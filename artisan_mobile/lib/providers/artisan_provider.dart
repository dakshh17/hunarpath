import 'dart:io';

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../models/models.dart';
import '../services/api_client.dart';
import '../services/audio_feedback_service.dart';

/// Central state controller for the artisan mobile app.
///
/// Manages authentication, artisan profile, dashboard metrics,
/// ingest pipeline results, orders, and demand alerts.
class ArtisanProvider extends ChangeNotifier {
  final ApiClient _api = ApiClient();
  final AudioFeedbackService _audio = AudioFeedbackService();

  // ── Auth state ─────────────────────────────────────────────────────
  bool isLoggedIn = false;
  bool isAuthLoading = true; // true until tryAutoLogin completes
  String? authError;

  // ── Profile (loaded from API after login) ──────────────────────────
  ArtisanProfile? _profile;
  ArtisanProfile get profile => _profile ?? const ArtisanProfile(
    id: '',
    name: '',
    clusterName: '',
  );

  DashboardMetrics metrics = const DashboardMetrics();
  bool isLoadingMetrics = false;

  // ── Ingest pipeline state ──────────────────────────────────────────
  bool isProcessing = false;
  String? processingError;

  IngestResult? lastIngestResult;
  double adjustedPrice = 0.0;

  // ── Demand radar ───────────────────────────────────────────────────
  List<DemandAlert> demandAlerts = [];
  bool isLoadingAlerts = false;

  // ── Orders ─────────────────────────────────────────────────────────
  List<OrderShare> orders = [];
  bool isLoadingOrders = false;

  // ── Initialisation ─────────────────────────────────────────────────

  ArtisanProvider() {
    tryAutoLogin();
  }

  @override
  void dispose() {
    _api.dispose();
    super.dispose();
  }

  // ── Authentication ─────────────────────────────────────────────────

  /// Try to restore a saved session from SharedPreferences.
  Future<void> tryAutoLogin() async {
    isAuthLoading = true;
    notifyListeners();

    try {
      final prefs = await SharedPreferences.getInstance();
      final token = prefs.getString('auth_token');
      final profileJson = prefs.getString('artisan_profile');

      if (token != null && profileJson != null) {
        _api.setAuthToken(token);

        // Try to validate the token by fetching the profile
        try {
          _profile = await _api.fetchProfile();
          isLoggedIn = true;
          _audio.init(dialect: _profile!.dialect);
        } catch (_) {
          // Token expired or invalid, clear stored data
          await _clearAuth();
        }
      }
    } catch (_) {
      // SharedPreferences error, continue as logged out
    }

    isAuthLoading = false;
    notifyListeners();
  }

  /// Login with phone number and PIN.
  Future<bool> login(String phone, String pin) async {
    authError = null;
    isAuthLoading = true;
    notifyListeners();

    try {
      final result = await _api.login(phone: phone, pin: pin);
      final token = result['token'] as String;
      final artisanJson = result['artisan'] as Map<String, dynamic>;

      _api.setAuthToken(token);
      _profile = ArtisanProfile.fromJson(artisanJson);
      isLoggedIn = true;

      // Persist session
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('auth_token', token);
      await prefs.setString('artisan_profile', token); // just for existence check

      _audio.init(dialect: _profile!.dialect);

      isAuthLoading = false;
      notifyListeners();
      return true;
    } on ApiException catch (e) {
      authError = e.message;
      isAuthLoading = false;
      notifyListeners();
      return false;
    } catch (e) {
      authError = 'Connection error. Is the server running?';
      isAuthLoading = false;
      notifyListeners();
      return false;
    }
  }

  /// Register a new artisan.
  Future<bool> register({
    required String name,
    required String phone,
    required String pin,
    String? location,
    String? clusterId,
    String dialect = 'hi',
    double dailyWage = 350.0,
  }) async {
    authError = null;
    isAuthLoading = true;
    notifyListeners();

    try {
      final result = await _api.register(
        name: name,
        phone: phone,
        pin: pin,
        location: location,
        clusterId: clusterId,
        dialect: dialect,
        dailyWage: dailyWage,
      );
      final token = result['token'] as String;
      final artisanJson = result['artisan'] as Map<String, dynamic>;

      _api.setAuthToken(token);
      _profile = ArtisanProfile.fromJson(artisanJson);
      isLoggedIn = true;

      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('auth_token', token);
      await prefs.setString('artisan_profile', token);

      _audio.init(dialect: _profile!.dialect);

      isAuthLoading = false;
      notifyListeners();
      return true;
    } on ApiException catch (e) {
      authError = e.message;
      isAuthLoading = false;
      notifyListeners();
      return false;
    } catch (e) {
      authError = 'Connection error. Is the server running?';
      isAuthLoading = false;
      notifyListeners();
      return false;
    }
  }

  /// Logout and clear stored credentials.
  Future<void> logout() async {
    await _clearAuth();
    _profile = null;
    isLoggedIn = false;
    metrics = const DashboardMetrics();
    orders = [];
    demandAlerts = [];
    lastIngestResult = null;
    notifyListeners();
  }

  Future<void> _clearAuth() async {
    _api.setAuthToken(null);
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove('auth_token');
      await prefs.remove('artisan_profile');
    } catch (_) {}
  }

  // ── Dashboard ──────────────────────────────────────────────────────

  /// Load dashboard metrics from the API.
  Future<void> loadDashboard() async {
    if (!isLoggedIn) return;
    isLoadingMetrics = true;
    notifyListeners();

    try {
      metrics = await _api.fetchDashboard();
    } catch (_) {
      // Keep existing metrics on error
    }

    isLoadingMetrics = false;
    notifyListeners();
  }

  // ── Orders ─────────────────────────────────────────────────────────

  /// Load order allocations from the API.
  Future<void> loadOrders() async {
    if (!isLoggedIn) return;
    isLoadingOrders = true;
    notifyListeners();

    try {
      orders = await _api.fetchOrders();
    } catch (_) {
      // Keep existing orders on error
    }

    isLoadingOrders = false;
    notifyListeners();
  }

  // ── Catalog Ingest ─────────────────────────────────────────────────

  /// Run the full ingest pipeline: image + audio → AI services.
  Future<void> ingestProduct({
    required File imageFile,
    required File audioFile,
  }) async {
    isProcessing = true;
    processingError = null;
    notifyListeners();

    await _audio.processingStarted();

    try {
      final result = await _api.ingestProduct(
        imageFile: imageFile,
        audioFile: audioFile,
        artisanId: profile.id,
        language: profile.dialect,
      );

      lastIngestResult = result;
      adjustedPrice = result.pricing.recommendedPrice;
      isProcessing = false;
      notifyListeners();

      await _audio.processingComplete();
    } catch (e) {
      isProcessing = false;
      processingError = e.toString();
      notifyListeners();
      await _audio.errorOccurred();
    }
  }

  // ── Price adjustment ───────────────────────────────────────────────

  void adjustPrice(double delta) {
    if (lastIngestResult == null) return;
    final newPrice = adjustedPrice + delta;
    if (newPrice >= lastIngestResult!.pricing.costFloor) {
      adjustedPrice = newPrice;
      notifyListeners();
    }
  }

  // ── Publish ────────────────────────────────────────────────────────

  /// Publish the reviewed product to the marketplace.
  Future<bool> publishProduct() async {
    if (lastIngestResult == null) return false;

    final catalog = lastIngestResult!.catalog;
    try {
      await _api.publishProduct(
        artisanId: profile.id,
        titleEn: catalog.titleEn ?? 'Handcrafted Product',
        titleHi: catalog.titleHi ?? 'हस्तनिर्मित उत्पाद',
        craftType: catalog.craftType ?? 'Handloom Weaving',
        material: catalog.material ?? 'Cotton',
        rawCost: catalog.rawCost ?? 0,
        laborDays: catalog.laborDays ?? 1,
        recommendedPrice: adjustedPrice,
        minMarketCorridor: lastIngestResult!.pricing.minMarketCorridor,
        maxMarketCorridor: lastIngestResult!.pricing.maxMarketCorridor,
      );

      metrics = DashboardMetrics(
        activeItems: metrics.activeItems + 1,
        totalOrders: metrics.totalOrders,
        totalEarnings: metrics.totalEarnings,
      );

      lastIngestResult = null;
      notifyListeners();

      await _audio.publishSuccess();
      return true;
    } catch (e) {
      await _audio.errorOccurred();
      return false;
    }
  }

  // ── Demand Radar ───────────────────────────────────────────────────

  Future<void> loadDemandAlerts() async {
    isLoadingAlerts = true;
    notifyListeners();

    try {
      demandAlerts = await _api.fetchDemandAlerts(
        dialect: profile.dialect,
      );
    } catch (_) {
      // Provide offline mock alerts
      demandAlerts = [
        const DemandAlert(
          craftCategory: 'Zari & Brocade',
          region: 'North India',
          searchCount: 18400,
          pctChange: 53,
          notification:
              'उत्तर भारत में ज़री और ब्रोकेड की माँग 53% बढ़ी है। लक्ष्य बाज़ार मूल्य: ₹2200।',
        ),
        const DemandAlert(
          craftCategory: 'Bell Metal Craft',
          region: 'Central India',
          searchCount: 5200,
          pctChange: 49,
          notification:
              'मध्य भारत में बेल मेटल की माँग 49% बढ़ी है। लक्ष्य बाज़ार मूल्य: ₹1800।',
        ),
      ];
    }

    isLoadingAlerts = false;
    notifyListeners();
  }

  /// Speak a demand alert aloud via TTS.
  Future<void> speakAlert(DemandAlert alert) async {
    await _audio.speak(alert.notification);
  }
}
