import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:path_provider/path_provider.dart';
import 'package:provider/provider.dart';
import 'package:record/record.dart';

import '../providers/artisan_provider.dart';
import '../services/audio_feedback_service.dart';
import '../theme/app_theme.dart';
import 'review_screen.dart';

/// Three-step capture flow:
///   1. Camera viewport → photograph the product.
///   2. Push-to-talk → record artisan description.
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

  int _step = 1; // 1 = camera, 2 = voice, 3 = processing
  File? _capturedImage;
  File? _recordedAudio;
  bool _isRecording = false;

  late AnimationController _pulseController;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat(reverse: true);

    // Speak camera instruction after build
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _audio.capturePhoto();
    });
  }

  @override
  void dispose() {
    _pulseController.dispose();
    _recorder.dispose();
    super.dispose();
  }

  // ── Step 1: Capture photo ──────────────────────────────────────────

  Future<void> _takePhoto() async {
    final XFile? xfile = await _picker.pickImage(
      source: ImageSource.camera,
      maxWidth: 2048,
      maxHeight: 2048,
      imageQuality: 95,
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
      maxWidth: 2048,
      maxHeight: 2048,
      imageQuality: 95,
    );
    if (xfile != null) {
      setState(() {
        _capturedImage = File(xfile.path);
        _step = 2;
      });
      await _audio.startRecording();
    }
  }

  // ── Step 2: Push-to-talk recording ─────────────────────────────────

  Future<void> _toggleRecording() async {
    if (_isRecording) {
      // Stop
      final path = await _recorder.stop();
      if (path != null) {
        setState(() {
          _recordedAudio = File(path);
          _isRecording = false;
        });
      }
    } else {
      // Start recording
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
        setState(() => _isRecording = true);
      }
    }
  }

  Future<void> _submitForProcessing() async {
    if (_capturedImage == null || _recordedAudio == null) return;

    setState(() => _step = 3);

    final provider = context.read<ArtisanProvider>();
    await provider.ingestProduct(
      imageFile: _capturedImage!,
      audioFile: _recordedAudio!,
    );

    if (!mounted) return;

    if (provider.processingError != null) {
      // Show error and go back to step 2
      setState(() => _step = 2);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(provider.processingError!),
            backgroundColor: AppTheme.dangerRed,
          ),
        );
      }
    } else {
      // Navigate to review
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
        return 'Step 1 · Photo';
      case 2:
        return 'Step 2 · Describe';
      case 3:
        return 'Processing…';
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
        // Viewport area with bounding-box overlay
        Expanded(
          child: Container(
            margin: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: Colors.grey.shade200,
              borderRadius: BorderRadius.circular(AppTheme.borderRadiusLg),
              border: Border.all(
                color: AppTheme.saffron.withOpacity(0.4),
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
                        color: AppTheme.saffron.withOpacity(0.3),
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
        // Action buttons
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
          child: Row(
            children: [
              // Gallery picker
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
              // Camera capture
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

  // ── Step 2 widget ──────────────────────────────────────────────────

  Widget _buildVoiceStep() {
    return Column(
      key: const ValueKey('step2'),
      children: [
        // Preview of captured image
        if (_capturedImage != null)
          Container(
            height: 200,
            margin: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(AppTheme.borderRadiusMd),
              image: DecorationImage(
                image: FileImage(_capturedImage!),
                fit: BoxFit.cover,
              ),
            ),
          ),

        const Spacer(),

        // Push-to-talk button
        Text(
          _isRecording ? 'Recording… Tap to stop' : 'Hold or tap to record',
          style: AppTheme.titleLarge,
        ),
        const SizedBox(height: 20),

        AnimatedBuilder(
          animation: _pulseController,
          builder: (context, child) {
            final scale = _isRecording
                ? 1.0 + (_pulseController.value * 0.12)
                : 1.0;
            return Transform.scale(
              scale: scale,
              child: child,
            );
          },
          child: GestureDetector(
            onTap: _toggleRecording,
            child: Container(
              width: 120,
              height: 120,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: _isRecording ? AppTheme.dangerRed : AppTheme.saffron,
                boxShadow: [
                  BoxShadow(
                    color: (_isRecording ? AppTheme.dangerRed : AppTheme.saffron)
                        .withOpacity(0.4),
                    blurRadius: 24,
                    spreadRadius: 4,
                  ),
                ],
              ),
              child: Icon(
                _isRecording ? Icons.stop_rounded : Icons.mic_rounded,
                color: Colors.white,
                size: 56,
              ),
            ),
          ),
        ),

        const Spacer(),

        // Submit button (visible once we have audio)
        if (_recordedAudio != null && !_isRecording)
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
            child: ElevatedButton.icon(
              onPressed: _submitForProcessing,
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.forest,
                minimumSize:
                    const Size(double.infinity, AppTheme.bigButtonHeight),
              ),
              icon: const Icon(Icons.auto_awesome_rounded, size: 28),
              label: const Text('Process with AI'),
            ),
          ),

        if (_recordedAudio == null || _isRecording)
          const SizedBox(height: AppTheme.bigButtonHeight + 24),
      ],
    );
  }

  // ── Step 3 widget ──────────────────────────────────────────────────

  Widget _buildProcessingStep() {
    return Center(
      key: const ValueKey('step3'),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          // Animated processing indicator
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
          const SizedBox(height: 32),
          const Text(
            'Enhancing your product…',
            style: AppTheme.headlineMedium,
          ),
          const SizedBox(height: 12),
          Text(
            'Building catalog & pricing',
            style: AppTheme.bodyLarge.copyWith(fontSize: 18),
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
    );
  }
}
