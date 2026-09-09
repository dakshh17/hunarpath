import 'package:flutter_tts/flutter_tts.dart';

/// Provides spoken audio feedback in the artisan's native dialect.
///
/// Every major action (capture, processing, publish, error) triggers a
/// voice confirmation so the artisan understands what happened without
/// needing to read on-screen text.
class AudioFeedbackService {
  static final AudioFeedbackService _instance = AudioFeedbackService._();
  factory AudioFeedbackService() => _instance;
  AudioFeedbackService._();

  final FlutterTts _tts = FlutterTts();
  String _currentLang = 'hi-IN';
  bool _initialised = false;

  /// Initialise the TTS engine with the given dialect.
  Future<void> init({String dialect = 'hi'}) async {
    if (_initialised) return;

    _currentLang = _dialectToLocale(dialect);
    await _tts.setLanguage(_currentLang);
    await _tts.setSpeechRate(0.45); // Slow & clear
    await _tts.setVolume(1.0);
    await _tts.setPitch(1.0);
    _initialised = true;
  }

  /// Speak a message aloud.  Cancels any in-progress speech first.
  Future<void> speak(String message) async {
    await _tts.stop();
    await _tts.speak(message);
  }

  /// Stop any ongoing speech.
  Future<void> stop() async {
    await _tts.stop();
  }

  /// Change dialect at runtime.
  Future<void> setDialect(String dialect) async {
    _currentLang = _dialectToLocale(dialect);
    await _tts.setLanguage(_currentLang);
  }

  // ── Canned feedback lines ──────────────────────────────────────────

  Future<void> welcomeGreeting(String name) async {
    await speak(_getLocalized(
      hi: 'नमस्ते $name जी, शिल्पसेतु में आपका स्वागत है',
      en: 'Welcome $name, to ShilpSetu',
      gu: 'નમસ્તે $name, શિલ્પસેતુમાં આપનું સ્વાગત છે',
    ));
  }

  Future<void> capturePhoto() async {
    await speak(_getLocalized(
      hi: 'अपने उत्पाद की फोटो खींचें',
      en: 'Take a photo of your product',
      gu: 'તમારા ઉત્પાદનો ફોટો લો',
    ));
  }

  Future<void> startRecording() async {
    await speak(_getLocalized(
      hi: 'अब अपने उत्पाद के बारे में बताएं',
      en: 'Now describe your product',
      gu: 'હવે તમારા ઉત્પાદ વિશે જણાવો',
    ));
  }

  Future<void> processingStarted() async {
    await speak(_getLocalized(
      hi: 'फोटो सुधार रहे हैं और कैटलॉग बना रहे हैं, कृपया प्रतीक्षा करें',
      en: 'Enhancing image and building catalog, please wait',
      gu: 'ફોટો સુધારી રહ્યા છીએ અને કેટલોગ બનાવી રહ્યા છીએ, કૃપા કરીને રાહ જુઓ',
    ));
  }

  Future<void> processingComplete() async {
    await speak(_getLocalized(
      hi: 'प्रोसेसिंग पूरी हुई, कृपया जानकारी जाँचें',
      en: 'Processing complete, please review the details',
      gu: 'પ્રોસેસિંગ પૂર્ણ થઈ, કૃપા કરીને વિગતો તપાસો',
    ));
  }

  Future<void> publishSuccess() async {
    await speak(_getLocalized(
      hi: 'बधाई हो! आपका उत्पाद बाज़ार में प्रकाशित हो गया है',
      en: 'Congratulations! Your product has been published to the marketplace',
      gu: 'અભિનંદન! તમારું ઉત્પાદ બજારમાં પ્રકાશિત થઈ ગયું છે',
    ));
  }

  Future<void> errorOccurred() async {
    await speak(_getLocalized(
      hi: 'कुछ गड़बड़ हुई, कृपया फिर से कोशिश करें',
      en: 'Something went wrong, please try again',
      gu: 'કંઈક ખોટું થયું, કૃપા કરીને ફરીથી પ્રયાસ કરો',
    ));
  }

  Future<void> speakProductSummary({
    required String title,
    required double rawCost,
    required double sellingPrice,
  }) async {
    await speak(_getLocalized(
      hi: 'उत्पाद: $title। कच्ची लागत: ${rawCost.toInt()} रुपये। '
          'सुझाई गई कीमत: ${sellingPrice.toInt()} रुपये',
      en: 'Product: $title. Raw cost: ${rawCost.toInt()} rupees. '
          'Suggested price: ${sellingPrice.toInt()} rupees',
      gu: 'ઉત્પાદ: $title। કાચી કિંમત: ${rawCost.toInt()} રૂપિયા। '
          'સૂચિત ભાવ: ${sellingPrice.toInt()} રૂપિયા',
    ));
  }

  // ── Helpers ────────────────────────────────────────────────────────

  String _dialectToLocale(String dialect) {
    const map = {
      'hi': 'hi-IN',
      'gu': 'gu-IN',
      'bn': 'bn-IN',
      'ta': 'ta-IN',
      'te': 'te-IN',
      'mr': 'mr-IN',
      'en': 'en-IN',
    };
    return map[dialect] ?? 'hi-IN';
  }

  String _getLocalized({
    required String hi,
    required String en,
    String? gu,
  }) {
    if (_currentLang.startsWith('gu') && gu != null) return gu;
    if (_currentLang.startsWith('en')) return en;
    return hi; // Default to Hindi
  }
}
