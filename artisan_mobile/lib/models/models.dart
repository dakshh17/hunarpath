import 'dart:convert';
import 'dart:typed_data';

/// Represents the artisan's profile and cluster affiliation.
class ArtisanProfile {
  final String id;
  final String name;
  final String phone;
  final String clusterId;
  final String clusterName;
  final String dialect; // ISO 639-1
  final double rating;
  final bool verified;

  const ArtisanProfile({
    required this.id,
    required this.name,
    this.phone = '',
    this.clusterId = '',
    required this.clusterName,
    this.dialect = 'hi',
    this.rating = 4.8,
    this.verified = true,
  });

  factory ArtisanProfile.fromJson(Map<String, dynamic> json) {
    return ArtisanProfile(
      id: json['id'] as String,
      name: json['name'] as String,
      phone: json['phone'] as String? ?? '',
      clusterId: json['cluster_id'] as String? ?? '',
      clusterName: json['cluster_name'] as String,
      dialect: json['dialect'] as String? ?? 'hi',
      rating: (json['rating'] as num?)?.toDouble() ?? 4.8,
      verified: json['verified'] as bool? ?? true,
    );
  }
}

/// Dashboard metrics for the home screen.
class DashboardMetrics {
  final int activeItems;
  final int totalOrders;
  final double totalEarnings;

  const DashboardMetrics({
    this.activeItems = 0,
    this.totalOrders = 0,
    this.totalEarnings = 0.0,
  });

  factory DashboardMetrics.fromJson(Map<String, dynamic> json) {
    return DashboardMetrics(
      activeItems: json['active_items'] as int? ?? 0,
      totalOrders: json['total_orders'] as int? ?? 0,
      totalEarnings: (json['total_earnings'] as num?)?.toDouble() ?? 0.0,
    );
  }
}

/// Pricing recommendation from the backend.
class PriceRecommendation {
  final double costFloor;
  final double recommendedPrice;
  final double minMarketCorridor;
  final double maxMarketCorridor;
  final double netArtisanMargin;
  final String pricingMethod;

  const PriceRecommendation({
    required this.costFloor,
    required this.recommendedPrice,
    required this.minMarketCorridor,
    required this.maxMarketCorridor,
    required this.netArtisanMargin,
    this.pricingMethod = 'heuristic',
  });

  factory PriceRecommendation.fromJson(Map<String, dynamic> json) {
    return PriceRecommendation(
      costFloor: (json['cost_floor'] as num).toDouble(),
      recommendedPrice: (json['recommended_price'] as num).toDouble(),
      minMarketCorridor: (json['min_market_corridor'] as num).toDouble(),
      maxMarketCorridor: (json['max_market_corridor'] as num).toDouble(),
      netArtisanMargin: (json['net_artisan_margin'] as num).toDouble(),
      pricingMethod: json['pricing_method'] as String? ?? 'heuristic',
    );
  }
}

/// Structured catalog metadata extracted from the artisan's voice note.
class CatalogMetadata {
  final String? craftType;
  final String? material;
  final String? primaryColor;
  final double? laborDays;
  final double? rawCost;
  final String? titleEn;
  final String? titleHi;
  final String? descriptionEn;
  final String? descriptionHi;

  const CatalogMetadata({
    this.craftType,
    this.material,
    this.primaryColor,
    this.laborDays,
    this.rawCost,
    this.titleEn,
    this.titleHi,
    this.descriptionEn,
    this.descriptionHi,
  });

  factory CatalogMetadata.fromJson(Map<String, dynamic> json) {
    return CatalogMetadata(
      craftType: json['craft_type'] as String?,
      material: json['material'] as String?,
      primaryColor: json['primary_color'] as String?,
      laborDays: (json['labor_days'] as num?)?.toDouble(),
      rawCost: (json['raw_cost'] as num?)?.toDouble(),
      titleEn: json['title_en'] as String?,
      titleHi: json['title_hi'] as String?,
      descriptionEn: json['description_en'] as String?,
      descriptionHi: json['description_hi'] as String?,
    );
  }
}

/// Full response from /api/v1/catalog/ingest.
class IngestResult {
  final Uint8List studioImageBytes;
  final String rawTranscript;
  final CatalogMetadata catalog;
  final PriceRecommendation pricing;
  final String artisanId;

  const IngestResult({
    required this.studioImageBytes,
    required this.rawTranscript,
    required this.catalog,
    required this.pricing,
    required this.artisanId,
  });

  factory IngestResult.fromJson(Map<String, dynamic> json) {
    final imageB64 = json['studio_image_base64'] as String;
    return IngestResult(
      studioImageBytes: base64Decode(imageB64),
      rawTranscript: json['raw_transcript'] as String,
      catalog: CatalogMetadata.fromJson(
        json['catalog_metadata'] as Map<String, dynamic>,
      ),
      pricing: PriceRecommendation.fromJson(
        json['price_recommendation'] as Map<String, dynamic>,
      ),
      artisanId: json['artisan_id'] as String,
    );
  }
}

/// A single demand alert from the demand radar.
class DemandAlert {
  final String craftCategory;
  final String region;
  final int searchCount;
  final int pctChange;
  final String notification;

  const DemandAlert({
    required this.craftCategory,
    required this.region,
    required this.searchCount,
    required this.pctChange,
    required this.notification,
  });

  factory DemandAlert.fromJson(Map<String, dynamic> json) {
    return DemandAlert(
      craftCategory: json['craft_category'] as String,
      region: json['region'] as String,
      searchCount: json['search_count'] as int,
      pctChange: json['pct_change'] as int,
      notification: json['notification'] as String,
    );
  }
}

/// An allocated order share from an RFQ.
class OrderShare {
  final String rfqId;
  final String buyerName;
  final int allocatedUnits;
  final double payoutAmount;
  final String status;

  const OrderShare({
    required this.rfqId,
    required this.buyerName,
    required this.allocatedUnits,
    required this.payoutAmount,
    this.status = 'ALLOCATED',
  });

  factory OrderShare.fromJson(Map<String, dynamic> json) {
    return OrderShare(
      rfqId: json['rfq_id'] as String,
      buyerName: json['buyer_name'] as String,
      allocatedUnits: json['allocated_units'] as int,
      payoutAmount: (json['payout_amount'] as num).toDouble(),
      status: json['status'] as String? ?? 'ALLOCATED',
    );
  }
}
