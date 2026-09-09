import 'package:flutter/material.dart';

/// High-contrast tactile theme for rural artisan accessibility.
///
/// Design directives:
/// - Minimum 64dp touch targets everywhere
/// - Bold, large typography
/// - High-contrast colour pairs (WCAG AAA)
/// - Warm earth-toned palette reflecting Indian craft heritage
class AppTheme {
  AppTheme._();

  // ── Palette ────────────────────────────────────────────────────────
  static const Color saffron = Color(0xFFE8752A);
  static const Color saffronDark = Color(0xFFC45E1A);
  static const Color forest = Color(0xFF1B7A3D);
  static const Color forestDark = Color(0xFF145E2E);
  static const Color ivory = Color(0xFFFFF8F0);
  static const Color warmWhite = Color(0xFFFFFDF9);
  static const Color charcoal = Color(0xFF212121);
  static const Color slate = Color(0xFF5A5A5A);
  static const Color dangerRed = Color(0xFFD32F2F);
  static const Color successGreen = Color(0xFF2E7D32);
  static const Color cardShadow = Color(0x1A000000);

  // ── Touch target minimums ──────────────────────────────────────────
  static const double minTouchHeight = 64.0;
  static const double bigButtonHeight = 72.0;
  static const double iconSizeLarge = 36.0;
  static const double iconSizeXL = 48.0;
  static const double borderRadiusLg = 20.0;
  static const double borderRadiusMd = 14.0;

  // ── Typography ─────────────────────────────────────────────────────
  static const String? _fontFamily = null;

  static const TextStyle headlineLarge = TextStyle(
    fontFamily: _fontFamily,
    fontSize: 28,
    fontWeight: FontWeight.w700,
    color: charcoal,
    height: 1.3,
  );

  static const TextStyle headlineMedium = TextStyle(
    fontFamily: _fontFamily,
    fontSize: 22,
    fontWeight: FontWeight.w700,
    color: charcoal,
    height: 1.3,
  );

  static const TextStyle titleLarge = TextStyle(
    fontFamily: _fontFamily,
    fontSize: 18,
    fontWeight: FontWeight.w600,
    color: charcoal,
  );

  static const TextStyle bodyLarge = TextStyle(
    fontFamily: _fontFamily,
    fontSize: 16,
    fontWeight: FontWeight.w400,
    color: slate,
  );

  static const TextStyle bodyBold = TextStyle(
    fontFamily: _fontFamily,
    fontSize: 16,
    fontWeight: FontWeight.w700,
    color: charcoal,
  );

  static const TextStyle labelLarge = TextStyle(
    fontFamily: _fontFamily,
    fontSize: 14,
    fontWeight: FontWeight.w600,
    color: slate,
  );

  static const TextStyle metricValue = TextStyle(
    fontFamily: _fontFamily,
    fontSize: 32,
    fontWeight: FontWeight.w700,
    color: charcoal,
    height: 1.1,
  );

  // ── ThemeData ──────────────────────────────────────────────────────
  static ThemeData get lightTheme => ThemeData(
        useMaterial3: true,
        fontFamily: _fontFamily,
        scaffoldBackgroundColor: ivory,
        colorScheme: ColorScheme.fromSeed(
          seedColor: saffron,
          brightness: Brightness.light,
          primary: saffron,
          onPrimary: Colors.white,
          secondary: forest,
          onSecondary: Colors.white,
          surface: warmWhite,
          onSurface: charcoal,
          error: dangerRed,
        ),
        appBarTheme: const AppBarTheme(
          backgroundColor: saffron,
          foregroundColor: Colors.white,
          elevation: 0,
          centerTitle: false,
          titleTextStyle: TextStyle(
            fontFamily: _fontFamily,
            fontSize: 20,
            fontWeight: FontWeight.w700,
            color: Colors.white,
          ),
        ),
        elevatedButtonTheme: ElevatedButtonThemeData(
          style: ElevatedButton.styleFrom(
            backgroundColor: saffron,
            foregroundColor: Colors.white,
            minimumSize: const Size(double.infinity, bigButtonHeight),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(borderRadiusMd),
            ),
            textStyle: const TextStyle(
              fontFamily: _fontFamily,
              fontSize: 18,
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
        outlinedButtonTheme: OutlinedButtonThemeData(
          style: OutlinedButton.styleFrom(
            foregroundColor: saffron,
            minimumSize: const Size(double.infinity, minTouchHeight),
            side: const BorderSide(color: saffron, width: 2),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(borderRadiusMd),
            ),
            textStyle: const TextStyle(
              fontFamily: _fontFamily,
              fontSize: 16,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
        cardTheme: CardThemeData(
          color: warmWhite,
          elevation: 2,
          shadowColor: cardShadow,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(borderRadiusLg),
          ),
          margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        ),
        floatingActionButtonTheme: const FloatingActionButtonThemeData(
          backgroundColor: saffron,
          foregroundColor: Colors.white,
          extendedTextStyle: TextStyle(
            fontFamily: _fontFamily,
            fontSize: 18,
            fontWeight: FontWeight.w700,
          ),
        ),
      );
}
