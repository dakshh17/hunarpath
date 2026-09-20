import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:path_provider/path_provider.dart';
import 'package:provider/provider.dart';
import 'package:record/record.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;

import '../providers/artisan_provider.dart';
import '../services/audio_feedback_service.dart';
import '../theme/app_theme.dart';
import 'review_screen.dart';

/// Three-step capture flow:
///   1. Camera viewport → photograph the product.
///   2. Push-to-talk → live transcript in artisan's native language + audio recording.
///   3. Loading animation → AI processing with spoken status.
class CaptureScreen extends StatefulWidget {
  const CaptureScreen({super.key});

  @override
  State<CaptureScreen> createState() => _CaptureScreenState();
}

class _CaptureScreenState extends State<CaptureScreen>
    with SingleTickerProviderStateMixin {
  final _audio = AudioFeedbackService();
  final _picker = ImagePicker();
  final _recorder = AudioRecorder();
  final _speech = stt.SpeechToText();

  int _step = 1; // 1 = camera, 2 = voice, 3 = processing
  File? _capturedImage;
  File? _recordedAudio;
  bool _isRecording = false;
  bool _speechEnabled = false;
  bool _isTranscribing = false;

  String _liveTranscript = '';
  final _transcriptController = TextEditingController();

  late AnimationController _pulseController;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat(reverse: true);

    _initSpeech();

    // Speak camera instruction after build
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _audio.capturePhoto();
    });
  }

  Future<void> _initSpeech() async {
    try {
      _speechEnabled = await _speech.initialize(
        onError: (val) => debugPrint('SpeechToText Error: $val'),
        onStatus: (val) => debugPrint('SpeechToText Status: $val'),
      );
      if (mounted) setState(() {});
    } catch (e) {
      debugPrint('SpeechToText initialization failed: $e');
    }
  }

  @override
  void dispose() {
    _pulseController.dispose();
    _recorder.dispose();
    _speech.stop();
    _transcriptController.dispose();
    super.dispose();
  }

  // ── Step 1: Capture photo ──────────────────────────────────────────

  Future<void> _takePhoto() async {
    final XFile? xfile = await _picker.pickImage(
      source: ImageSource.camera,
      maxWidth: 1024,
      maxHeight: 1024,
      imageQuality: 80,
    );
    if (xfile != null) {
      setState(() {
        _capturedImage = File(xfile.path);
        _step = 2;
      });
      await _audio.startRecording();
    }
  }

  Future<void> _pickFromGallery() async {
    final XFile? xfile = await _picker.pickImage(
      source: ImageSource.gallery,
      maxWidth: 1024,
      maxHeight: 1024,
      imageQuality: 80,
    );
    if (xfile != null) {
      setState(() {
        _capturedImage = File(xfile.path);
        _step = 2;
      });
      await _audio.startRecording();
    }
  }

  // ── Step 2: Push-to-talk recording with live speech-to-text ────────

  String _getLocaleForDialect(String dialect) {
    switch (dialect.toLowerCase()) {
      case 'gu':
        return 'gu_IN';
      case 'bn':
        return 'bn_IN';
      case 'en':
        return 'en_IN';
      case 'hi':
      default:
        return 'hi_IN';
    }
  }

  Future<void> _toggleRecording() async {
    if (_isRecording) {
      // ── Stop recording ─────────────────────────────────────────────
      setState(() => _isRecording = false);

      if (_speech.isListening) {
        await _speech.stop();
      }

      String? audioPath;
      try {
        audioPath = await _recorder.stop();
      } catch (_) {}

      if (audioPath != null) {
        _recordedAudio = File(audioPath);
      }

      if (_liveTranscript.trim().isNotEmpty) {
        _transcriptController.text = _liveTranscript.trim();
      }

      // If on-device speech captured nothing, but audio was recorded, transcribe via Groq Whisper backend
      if (_transcriptController.text.trim().isEmpty && _recordedAudio != null) {
        if (!mounted) return;
        setState(() => _isTranscribing = true);
        try {
          final provider = context.read<ArtisanProvider>();
          final text = await provider.transcribeAudio(_recordedAudio!);
          if (text.trim().isNotEmpty && mounted) {
            setState(() {
              _liveTranscript = text.trim();
              _transcriptController.text = text.trim();
            });
          }
        } catch (e) {
          debugPrint('Backend transcription fallback error: $e');
        } finally {
          if (mounted) setState(() => _isTranscribing = false);
        }
      }
    } else {
      // ── Start recording ────────────────────────────────────────────
      setState(() {
        _liveTranscript = '';
        _transcriptController.clear();
        _recordedAudio = null;
        _isRecording = true;
      });

      final dialect = context.read<ArtisanProvider>().profile.dialect;
      final localeId = _getLocaleForDialect(dialect);

      bool listened = false;
      if (_speechEnabled) {
        try {
          listened = await _speech.listen(
            localeId: localeId,
            onResult: (result) {
              if (mounted) {
                setState(() {
                  _liveTranscript = result.recognizedWords;
                  _transcriptController.text = result.recognizedWords;
                });
              }
            },
            listenOptions: stt.SpeechListenOptions(
              listenMode: stt.ListenMode.dictation,
              partialResults: true,
              cancelOnError: false,
              listenFor: const Duration(minutes: 2),
              pauseFor: const Duration(seconds: 10),
            ),
          );
        } catch (e) {
          debugPrint('Speech listen error: $e');
          listened = false;
        }
      }

      // If on-device speech recognizer is not active/supported on this device,
      // record audio so we can transcribe with backend Groq Whisper upon stopping!
      if (!listened) {
        try {
          final tempDir = await getTemporaryDirectory();
          final filePath =
              '${tempDir.path}/artisan_voice_${DateTime.now().millisecondsSinceEpoch}.wav';
          if (await _recorder.hasPermission()) {
            await _recorder.start(
              const RecordConfig(
                encoder: AudioEncoder.wav,
                sampleRate: 16000,
                numChannels: 1,
              ),
              path: filePath,
            );
          }
        } catch (e) {
          debugPrint('Audio recorder error: $e');
        }
      }
    }
  }

  Future<void> _submitForProcessing() async {
    if (_capturedImage == null) return;
    final transcriptText = _transcriptController.text.trim();

    if (_recordedAudio == null && transcriptText.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('कृपया उत्पाद का विवरण बोलें (Please describe your product)'),
        ),
      );
      return;
    }

    setState(() => _step = 3);

    final provider = context.read<ArtisanProvider>();
    await provider.ingestProduct(
      imageFile: _capturedImage!,
      audioFile: _recordedAudio,
      transcript: transcriptText.isNotEmpty ? transcriptText : null,
    );

    if (!mounted) return;

    if (provider.processingError != null) {
      setState(() => _step = 2);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(provider.processingError!),
            backgroundColor: AppTheme.dangerRed,
            duration: const Duration(seconds: 4),
          ),
        );
      }
    } else {
      if (mounted) {
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(builder: (_) => const ReviewScreen()),
        );
      }
    }
  }

  // ── Build ──────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_stepTitle()),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_rounded, size: 28),
          onPressed: () {
            if (_step > 1 && _step < 3) {
              setState(() => _step -= 1);
            } else {
              Navigator.pop(context);
            }
          },
        ),
      ),
      body: SafeArea(
        child: AnimatedSwitcher(
          duration: const Duration(milliseconds: 300),
          child: _buildStep(),
        ),
      ),
    );
  }

  String _stepTitle() {
    switch (_step) {
      case 1:
        return 'Step 1 · Photo (तस्वीर)';
      case 2:
        return 'Step 2 · Speak (विवरण बोलें)';
      case 3:
        return 'AI Studio Processing…';
      default:
        return 'Capture';
    }
  }

  Widget _buildStep() {
    switch (_step) {
      case 1:
        return _buildCameraStep();
      case 2:
        return _buildVoiceStep();
      case 3:
        return _buildProcessingStep();
      default:
        return const SizedBox.shrink();
    }
  }

  // ── Step 1 widget ──────────────────────────────────────────────────

  Widget _buildCameraStep() {
    return Column(
      key: const ValueKey('step1'),
      children: [
        Expanded(
          child: Container(
            margin: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: Colors.grey.shade200,
              borderRadius: BorderRadius.circular(AppTheme.borderRadiusLg),
              border: Border.all(
                color: AppTheme.saffron.withValues(alpha: 0.4),
                width: 3,
              ),
            ),
            child: _capturedImage != null
                ? ClipRRect(
                    borderRadius: BorderRadius.circular(AppTheme.borderRadiusLg - 2),
                    child: Image.file(
                      _capturedImage!,
                      fit: BoxFit.contain,
                      width: double.infinity,
                      height: double.infinity,
                    ),
                  )
                : Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(
                        Icons.crop_free_rounded,
                        size: 100,
                        color: AppTheme.saffron.withValues(alpha: 0.3),
                      ),
                      const SizedBox(height: 16),
                      Text(
                        'Place product inside frame',
                        style: AppTheme.titleLarge.copyWith(
                          color: AppTheme.slate,
                        ),
                      ),
                    ],
                  ),
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
          child: Row(
            children: [
              Expanded(
                child: SizedBox(
                  height: AppTheme.bigButtonHeight,
                  child: OutlinedButton.icon(
                    onPressed: _pickFromGallery,
                    icon: const Icon(Icons.photo_library_rounded, size: 28),
                    label: const Text('Gallery'),
                  ),
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                flex: 2,
                child: SizedBox(
                  height: AppTheme.bigButtonHeight,
                  child: ElevatedButton.icon(
                    onPressed: _takePhoto,
                    icon: const Icon(Icons.camera_alt_rounded, size: 28),
                    label: const Text('Take Photo'),
                  ),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  // ── Step 2 widget (Live Transcript in native language) ─────────────

  Widget _buildVoiceStep() {
    final hasContent = _liveTranscript.isNotEmpty ||
        _transcriptController.text.isNotEmpty ||
        _recordedAudio != null;

    return SingleChildScrollView(
      key: const ValueKey('step2'),
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Thumbnail of photo
          if (_capturedImage != null)
            Center(
              child: Container(
                height: 140,
                width: 140,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(16),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withValues(alpha: 0.1),
                      blurRadius: 10,
                    ),
                  ],
                  image: DecorationImage(
                    image: FileImage(_capturedImage!),
                    fit: BoxFit.cover,
                  ),
                ),
              ),
            ),
          const SizedBox(height: 16),

          // ── Live Speech Transcript Box ─────────────────────────────
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: _isRecording ? const Color(0xFFFFF7ED) : Colors.white,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                color: _isRecording ? AppTheme.saffron : Colors.grey.shade300,
                width: _isRecording ? 2.0 : 1.0,
              ),
              boxShadow: [
                BoxShadow(
                  color: _isRecording
                      ? AppTheme.saffron.withValues(alpha: 0.15)
                      : Colors.black.withValues(alpha: 0.04),
                  blurRadius: 12,
                ),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Row(
                      children: [
                        if (_isRecording)
                          Container(
                            width: 10,
                            height: 10,
                            margin: const EdgeInsets.only(right: 8),
                            decoration: const BoxDecoration(
                              color: Colors.red,
                              shape: BoxShape.circle,
                            ),
                          ),
                        Text(
                          _isRecording
                              ? 'बोलिए, हम सुन रहे हैं (Listening…)'
                              : 'विवरण (Product Description):',
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.bold,
                            color: _isRecording ? Colors.red.shade700 : AppTheme.slate,
                          ),
                        ),
                      ],
                    ),
                    if (!_isRecording && _transcriptController.text.isNotEmpty)
                      IconButton(
                        icon: const Icon(Icons.clear_rounded, size: 20, color: AppTheme.slate),
                        tooltip: 'Clear',
                        onPressed: () {
                          setState(() {
                            _liveTranscript = '';
                            _transcriptController.clear();
                            _recordedAudio = null;
                          });
                        },
                      ),
                  ],
                ),
                const SizedBox(height: 10),
                if (_isTranscribing)
                  const Padding(
                    padding: EdgeInsets.symmetric(vertical: 12),
                    child: Row(
                      children: [
                        SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(
                            strokeWidth: 2.5,
                            color: AppTheme.saffron,
                          ),
                        ),
                        SizedBox(width: 12),
                        Text(
                          'AI से लिख रहे हैं... (Transcribing with AI…)',
                          style: TextStyle(
                            fontSize: 15,
                            fontStyle: FontStyle.italic,
                            color: AppTheme.slate,
                          ),
                        ),
                      ],
                    ),
                  )
                else if (_isRecording)
                  Text(
                    _liveTranscript.isNotEmpty
                        ? _liveTranscript
                        : 'सुन रहे हैं... कृपया बोलें (Listening... please speak)',
                    style: TextStyle(
                      fontSize: 18,
                      height: 1.4,
                      fontWeight: FontWeight.w600,
                      color: _liveTranscript.isNotEmpty
                          ? const Color(0xFF1E293B)
                          : Colors.grey.shade500,
                    ),
                  )
                else
                  TextField(
                    controller: _transcriptController,
                    maxLines: 4,
                    minLines: 2,
                    decoration: InputDecoration(
                      hintText: 'माइक दबाकर बोलें या यहाँ लिखें (Tap mic to speak or type here)...',
                      hintStyle: TextStyle(color: Colors.grey.shade400, fontSize: 16),
                      border: InputBorder.none,
                      isDense: true,
                    ),
                    style: const TextStyle(
                      fontSize: 17,
                      height: 1.4,
                      color: Color(0xFF1E293B),
                      fontWeight: FontWeight.w500,
                    ),
                  ),
              ],
            ),
          ),

          const SizedBox(height: 24),

          // ── Push-to-talk Mic Button ────────────────────────────────
          Center(
            child: Column(
              children: [
                Text(
                  _isRecording ? 'रोकने के लिए दबाएं (Tap to stop)' : 'बोलने के लिए दबाएं (Tap to speak)',
                  style: AppTheme.titleLarge.copyWith(
                    color: _isRecording ? AppTheme.dangerRed : AppTheme.charcoal,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 16),
                AnimatedBuilder(
                  animation: _pulseController,
                  builder: (context, child) {
                    final scale = _isRecording
                        ? 1.0 + (_pulseController.value * 0.14)
                        : 1.0;
                    return Transform.scale(
                      scale: scale,
                      child: child,
                    );
                  },
                  child: GestureDetector(
                    onTap: _toggleRecording,
                    child: Container(
                      width: 100,
                      height: 100,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: _isRecording ? AppTheme.dangerRed : AppTheme.saffron,
                        boxShadow: [
                          BoxShadow(
                            color: (_isRecording ? AppTheme.dangerRed : AppTheme.saffron)
                                .withValues(alpha: 0.4),
                            blurRadius: 20,
                            spreadRadius: 4,
                          ),
                        ],
                      ),
                      child: Icon(
                        _isRecording ? Icons.stop_rounded : Icons.mic_rounded,
                        color: Colors.white,
                        size: 50,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),

          const SizedBox(height: 24),

          // ── Submit Button ──────────────────────────────────────────
          if (hasContent && !_isRecording)
            ElevatedButton.icon(
              onPressed: _submitForProcessing,
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.forest,
                minimumSize: const Size(double.infinity, AppTheme.bigButtonHeight),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
              icon: const Icon(Icons.auto_awesome_rounded, size: 28, color: Colors.white),
              label: const Text(
                'AI के साथ तैयार करें (Process with AI)',
                style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold, color: Colors.white),
              ),
            ),
        ],
      ),
    );
  }

  // ── Step 3 widget (Fast Processing Screen) ─────────────────────────

  Widget _buildProcessingStep() {
    return Center(
      key: const ValueKey('step3'),
      child: Padding(
        padding: const EdgeInsets.all(32.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            AnimatedBuilder(
              animation: _pulseController,
              builder: (context, child) {
                return Opacity(
                  opacity: 0.5 + _pulseController.value * 0.5,
                  child: child,
                );
              },
              child: const Icon(
                Icons.auto_awesome_rounded,
                size: 80,
                color: AppTheme.saffron,
              ),
            ),
            const SizedBox(height: 24),
            const Text(
              'Creating Studio Lighting…',
              style: AppTheme.headlineMedium,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 8),
            Text(
              'Structuring your catalog & fair pricing',
              style: AppTheme.bodyLarge.copyWith(fontSize: 16),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 32),
            const SizedBox(
              width: 48,
              height: 48,
              child: CircularProgressIndicator(
                strokeWidth: 4,
                color: AppTheme.saffron,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

