import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';

import '../models/models.dart';

/// HTTP client for the ShilpSetu AI backend.
///
/// All methods include defensive error handling and return typed models.
class ApiClient {
  /// Backend base URL – use 10.0.2.2 for Android emulator → host localhost.
  static const String _baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://shilpsetu-1.onrender.com',
  );

  final http.Client _client;

  /// JWT auth token, set after login.
  String? _authToken;

  ApiClient({http.Client? client}) : _client = client ?? http.Client();

  void dispose() => _client.close();

  /// Set the JWT auth token for authenticated requests.
  void setAuthToken(String? token) {
    _authToken = token;
  }

  /// Build headers with optional auth token.
  Map<String, String> _headers({bool json = true}) {
    final headers = <String, String>{};
    if (json) headers['Content-Type'] = 'application/json';
    if (_authToken != null) {
      headers['Authorization'] = 'Bearer $_authToken';
    }
    return headers;
  }

  // ─────────────────────────────────────────────────────────────────
  // POST /api/v1/auth/login
  // ─────────────────────────────────────────────────────────────────

  /// Login with phone + PIN. Returns {token, artisan profile}.
  Future<Map<String, dynamic>> login({
    required String phone,
    required String pin,
  }) async {
    final uri = Uri.parse('$_baseUrl/api/v1/auth/login');
    final response = await _client.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'phone': phone, 'pin': pin}),
    );

    if (response.statusCode != 200) {
      final body = jsonDecode(response.body) as Map<String, dynamic>;
      throw ApiException(
        statusCode: response.statusCode,
        message: body['detail'] as String? ?? 'Login failed',
      );
    }

    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  // ─────────────────────────────────────────────────────────────────
  // POST /api/v1/auth/register
  // ─────────────────────────────────────────────────────────────────

  /// Register a new artisan. Returns {token, artisan profile}.
  Future<Map<String, dynamic>> register({
    required String name,
    required String phone,
    required String pin,
    required String clusterId,
    String dialect = 'hi',
    double dailyWage = 350.0,
  }) async {
    final uri = Uri.parse('$_baseUrl/api/v1/auth/register');
    final response = await _client.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'name': name,
        'phone': phone,
        'pin': pin,
        'cluster_id': clusterId,
        'dialect': dialect,
        'daily_wage': dailyWage,
      }),
    );

    if (response.statusCode != 200) {
      final body = jsonDecode(response.body) as Map<String, dynamic>;
      throw ApiException(
        statusCode: response.statusCode,
        message: body['detail'] as String? ?? 'Registration failed',
      );
    }

    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  // ─────────────────────────────────────────────────────────────────
  // GET /api/v1/artisan/me
  // ─────────────────────────────────────────────────────────────────

  /// Fetch the authenticated artisan's profile.
  Future<ArtisanProfile> fetchProfile() async {
    final uri = Uri.parse('$_baseUrl/api/v1/artisan/me');
    final response = await _client.get(uri, headers: _headers(json: false));

    if (response.statusCode != 200) {
      throw ApiException(
        statusCode: response.statusCode,
        message: 'Failed to fetch profile: ${response.body}',
      );
    }

    final json = jsonDecode(response.body) as Map<String, dynamic>;
    return ArtisanProfile.fromJson(json);
  }

  // ─────────────────────────────────────────────────────────────────
  // GET /api/v1/artisan/me/dashboard
  // ─────────────────────────────────────────────────────────────────

  /// Fetch dashboard metrics for the authenticated artisan.
  Future<DashboardMetrics> fetchDashboard() async {
    final uri = Uri.parse('$_baseUrl/api/v1/artisan/me/dashboard');
    final response = await _client.get(uri, headers: _headers(json: false));

    if (response.statusCode != 200) {
      throw ApiException(
        statusCode: response.statusCode,
        message: 'Failed to fetch dashboard: ${response.body}',
      );
    }

    final json = jsonDecode(response.body) as Map<String, dynamic>;
    return DashboardMetrics.fromJson(json);
  }

  // ─────────────────────────────────────────────────────────────────
  // GET /api/v1/artisan/me/orders
  // ─────────────────────────────────────────────────────────────────

  /// Fetch order allocations for the authenticated artisan.
  Future<List<OrderShare>> fetchOrders() async {
    final uri = Uri.parse('$_baseUrl/api/v1/artisan/me/orders');
    final response = await _client.get(uri, headers: _headers(json: false));

    if (response.statusCode != 200) {
      throw ApiException(
        statusCode: response.statusCode,
        message: 'Failed to fetch orders: ${response.body}',
      );
    }

    final list = jsonDecode(response.body) as List<dynamic>;
    return list
        .map((e) => OrderShare.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  // ─────────────────────────────────────────────────────────────────
  // POST /api/v1/catalog/ingest
  // ─────────────────────────────────────────────────────────────────

  /// Sends a product image and artisan voice note for AI processing.
  Future<IngestResult> ingestProduct({
    required File imageFile,
    required File audioFile,
    required String artisanId,
    String language = 'hi',
  }) async {
    final uri = Uri.parse('$_baseUrl/api/v1/catalog/ingest');

    final request = http.MultipartRequest('POST', uri)
      ..fields['artisan_id'] = artisanId
      ..fields['language'] = language
      ..files.add(await http.MultipartFile.fromPath(
        'image',
        imageFile.path,
        contentType: MediaType('image', 'jpeg'),
      ))
      ..files.add(await http.MultipartFile.fromPath(
        'audio',
        audioFile.path,
        contentType: MediaType('audio', 'wav'),
      ));

    if (_authToken != null) {
      request.headers['Authorization'] = 'Bearer $_authToken';
    }

    final streamedResponse = await _client.send(request);
    final response = await http.Response.fromStream(streamedResponse);

    if (response.statusCode != 200) {
      throw ApiException(
        statusCode: response.statusCode,
        message: 'Catalog ingest failed: ${response.body}',
      );
    }

    final json = jsonDecode(response.body) as Map<String, dynamic>;
    return IngestResult.fromJson(json);
  }

  // ─────────────────────────────────────────────────────────────────
  // POST /api/v1/catalog/publish
  // ─────────────────────────────────────────────────────────────────

  /// Publishes an approved product to the marketplace.
  Future<Map<String, dynamic>> publishProduct({
    required String artisanId,
    required String titleEn,
    required String titleHi,
    required String craftType,
    required String material,
    required double rawCost,
    required double laborDays,
    required double recommendedPrice,
    required double minMarketCorridor,
    required double maxMarketCorridor,
    String? studioImagePath,
  }) async {
    final uri = Uri.parse('$_baseUrl/api/v1/catalog/publish');

    final body = {
      'artisan_id': artisanId,
      'title_en': titleEn,
      'title_hi': titleHi,
      'craft_type': craftType,
      'material': material,
      'raw_cost': rawCost,
      'labor_days': laborDays,
      'recommended_price': recommendedPrice,
      'min_market_corridor': minMarketCorridor,
      'max_market_corridor': maxMarketCorridor,
      'studio_image_path': studioImagePath,
      'is_active': true,
    };

    final response = await _client.post(
      uri,
      headers: _headers(),
      body: jsonEncode(body),
    );

    if (response.statusCode != 200) {
      throw ApiException(
        statusCode: response.statusCode,
        message: 'Publish failed: ${response.body}',
      );
    }

    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  // ─────────────────────────────────────────────────────────────────
  // GET /api/v1/demand-radar
  // ─────────────────────────────────────────────────────────────────

  /// Fetches trending demand alerts for the artisan's dialect.
  Future<List<DemandAlert>> fetchDemandAlerts({
    String? clusterId,
    String dialect = 'hi',
  }) async {
    final params = <String, String>{
      'dialect': dialect,
      'limit': '5',
    };
    if (clusterId != null) params['cluster_id'] = clusterId;

    final uri = Uri.parse('$_baseUrl/api/v1/demand-radar')
        .replace(queryParameters: params);

    final response = await _client.get(uri, headers: _headers(json: false));

    if (response.statusCode != 200) {
      throw ApiException(
        statusCode: response.statusCode,
        message: 'Demand radar failed: ${response.body}',
      );
    }

    final json = jsonDecode(response.body) as Map<String, dynamic>;
    final alerts = (json['alerts'] as List)
        .map((a) => DemandAlert.fromJson(a as Map<String, dynamic>))
        .toList();
    return alerts;
  }

  // ─────────────────────────────────────────────────────────────────
  // GET /api/v1/clusters/map
  // ─────────────────────────────────────────────────────────────────

  /// Returns the raw GeoJSON feature collection of clusters.
  Future<Map<String, dynamic>> fetchClustersGeoJSON() async {
    final uri = Uri.parse('$_baseUrl/api/v1/clusters/map');
    final response = await _client.get(uri);

    if (response.statusCode != 200) {
      throw ApiException(
        statusCode: response.statusCode,
        message: 'Clusters map failed: ${response.body}',
      );
    }

    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  // ─────────────────────────────────────────────────────────────────
  // GET /healthz
  // ─────────────────────────────────────────────────────────────────

  /// Simple liveness check.
  Future<bool> healthCheck() async {
    try {
      final uri = Uri.parse('$_baseUrl/healthz');
      final response =
          await _client.get(uri).timeout(const Duration(seconds: 5));
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }
}

/// Typed API error.
class ApiException implements Exception {
  final int statusCode;
  final String message;

  const ApiException({required this.statusCode, required this.message});

  @override
  String toString() => 'ApiException($statusCode): $message';
}
