import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/models.dart';
import '../providers/artisan_provider.dart';
import '../services/audio_feedback_service.dart';
import '../theme/app_theme.dart';
import 'capture_screen.dart';
import 'orders_screen.dart';

/// Home dashboard with artisan status, metric cards, primary "Add Product"
/// action, and demand radar audio alerts.
class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final _audio = AudioFeedbackService();

  @override
  void initState() {
    super.initState();
    // Fire a welcome greeting after the first frame
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final provider = context.read<ArtisanProvider>();
      _audio.init(dialect: provider.profile.dialect);
      _audio.welcomeGreeting(provider.profile.name);
      provider.loadDashboard();
      provider.loadDemandAlerts();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<ArtisanProvider>(
      builder: (context, provider, _) {
        final profile = provider.profile;
        final metrics = provider.metrics;

        return Scaffold(
          appBar: AppBar(
            title: const Text('ShilpSetu'),
            actions: [
              IconButton(
                icon: const Icon(Icons.assignment, size: AppTheme.iconSizeLarge),
                tooltip: 'Orders',
                onPressed: () => Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => const OrdersScreen()),
                ),
              ),
              IconButton(
                icon: const Icon(Icons.logout, size: AppTheme.iconSizeLarge),
                tooltip: 'Logout',
                onPressed: () => provider.logout(),
              ),
            ],
          ),
          body: SafeArea(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(vertical: 16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // ── Artisan status header ──────────────────────────
                  _ArtisanStatusCard(
                    name: profile.name,
                    clusterName: profile.clusterName,
                    rating: profile.rating,
                    verified: profile.verified,
                  ),

                  const SizedBox(height: 12),

                  // ── Metric cards row ───────────────────────────────
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    child: Row(
                      children: [
                        Expanded(
                          child: _MetricCard(
                            icon: Icons.inventory_2_rounded,
                            label: 'Active Items',
                            value: '${metrics.activeItems}',
                            color: AppTheme.saffron,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: _MetricCard(
                            icon: Icons.shopping_cart_rounded,
                            label: 'Orders',
                            value: '${metrics.totalOrders}',
                            color: AppTheme.forest,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: _MetricCard(
                            icon: Icons.account_balance_wallet_rounded,
                            label: 'Earnings',
                            value: '₹${metrics.totalEarnings.toInt()}',
                            color: const Color(0xFF6A1B9A),
                          ),
                        ),
                      ],
                    ),
                  ),

                  const SizedBox(height: 24),

                  // ── Add Product banner ─────────────────────────────
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    child: _AddProductBanner(
                      onTap: () => Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => const CaptureScreen(),
                        ),
                      ),
                    ),
                  ),

                  const SizedBox(height: 24),

                  // ── Demand Radar card ──────────────────────────────
                  _DemandRadarSection(
                    alerts: provider.demandAlerts,
                    isLoading: provider.isLoadingAlerts,
                    onPlayAlert: provider.speakAlert,
                    onRefresh: provider.loadDemandAlerts,
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}

// ═════════════════════════════════════════════════════════════════════════════
// WIDGETS
// ═════════════════════════════════════════════════════════════════════════════

/// Prominent artisan name + cluster badge + rating stars.
class _ArtisanStatusCard extends StatelessWidget {
  final String name;
  final String clusterName;
  final double rating;
  final bool verified;

  const _ArtisanStatusCard({
    required this.name,
    required this.clusterName,
    required this.rating,
    required this.verified,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Row(
          children: [
            // Avatar
            CircleAvatar(
              radius: 32,
              backgroundColor: AppTheme.saffron.withOpacity(0.15),
              child: Text(
                name.isNotEmpty ? name[0] : '?',
                style: AppTheme.headlineLarge.copyWith(color: AppTheme.saffron),
              ),
            ),
            const SizedBox(width: 16),
            // Name & cluster
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(name, style: AppTheme.headlineMedium),
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      if (verified)
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 8,
                            vertical: 3,
                          ),
                          decoration: BoxDecoration(
                            color: AppTheme.successGreen,
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: const Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Icon(Icons.verified, color: Colors.white, size: 14),
                              SizedBox(width: 4),
                              Text(
                                'Verified',
                                style: TextStyle(
                                  color: Colors.white,
                                  fontSize: 12,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                            ],
                          ),
                        ),
                      const SizedBox(width: 8),
                      Icon(Icons.star_rounded,
                          color: Colors.amber.shade700, size: 18),
                      const SizedBox(width: 2),
                      Text(
                        rating.toStringAsFixed(1),
                        style: AppTheme.bodyBold,
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(clusterName, style: AppTheme.bodyLarge),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Single metric card with icon, value, and label.
class _MetricCard extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final Color color;

  const _MetricCard({
    required this.icon,
    required this.label,
    required this.value,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 18, horizontal: 12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(AppTheme.borderRadiusLg),
        boxShadow: const [
          BoxShadow(color: AppTheme.cardShadow, blurRadius: 6, offset: Offset(0, 2)),
        ],
      ),
      child: Column(
        children: [
          Icon(icon, color: color, size: 30),
          const SizedBox(height: 8),
          FittedBox(
            fit: BoxFit.scaleDown,
            child: Text(value, style: AppTheme.metricValue.copyWith(color: color)),
          ),
          const SizedBox(height: 4),
          Text(
            label,
            style: AppTheme.labelLarge,
            textAlign: TextAlign.center,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }
}

/// Oversized "Add Product" banner with camera + mic icons.
class _AddProductBanner extends StatelessWidget {
  final VoidCallback onTap;

  const _AddProductBanner({required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Material(
      color: AppTheme.saffron,
      borderRadius: BorderRadius.circular(AppTheme.borderRadiusLg),
      elevation: 4,
      child: InkWell(
        borderRadius: BorderRadius.circular(AppTheme.borderRadiusLg),
        onTap: onTap,
        child: Container(
          height: 110,
          padding: const EdgeInsets.symmetric(horizontal: 24),
          child: const Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.camera_alt_rounded, color: Colors.white, size: 40),
              SizedBox(width: 12),
              Icon(Icons.mic_rounded, color: Colors.white, size: 40),
              SizedBox(width: 20),
              Flexible(
                child: Text(
                  'Add Product',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 26,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Demand Radar section with one-tap audio alert cards.
class _DemandRadarSection extends StatelessWidget {
  final List<DemandAlert> alerts;
  final bool isLoading;
  final Future<void> Function(DemandAlert) onPlayAlert;
  final VoidCallback onRefresh;

  const _DemandRadarSection({
    required this.alerts,
    required this.isLoading,
    required this.onPlayAlert,
    required this.onRefresh,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.radar_rounded,
                  color: AppTheme.forest, size: AppTheme.iconSizeLarge),
              const SizedBox(width: 8),
              const Expanded(
                child: Text('Demand Radar', style: AppTheme.headlineMedium),
              ),
              IconButton(
                onPressed: onRefresh,
                icon: const Icon(Icons.refresh_rounded, size: 28),
                tooltip: 'Refresh',
              ),
            ],
          ),
          const SizedBox(height: 4),
          const Text(
            'Tap to hear what\'s trending',
            style: AppTheme.bodyLarge,
          ),
          const SizedBox(height: 12),
          if (isLoading)
            const Center(child: CircularProgressIndicator())
          else if (alerts.isEmpty)
            const Center(
              child: Padding(
                padding: EdgeInsets.all(24),
                child: Text(
                  'No alerts yet',
                  style: AppTheme.bodyLarge,
                ),
              ),
            )
          else
            ...alerts.map((alert) => _DemandAlertTile(
                  alert: alert,
                  onTap: () => onPlayAlert(alert),
                )),
        ],
      ),
    );
  }
}

/// A single demand alert tile with large speaker button.
class _DemandAlertTile extends StatelessWidget {
  final dynamic alert;
  final VoidCallback onTap;

  const _DemandAlertTile({required this.alert, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: InkWell(
        borderRadius: BorderRadius.circular(AppTheme.borderRadiusLg),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Container(
                width: 56,
                height: 56,
                decoration: BoxDecoration(
                  color: AppTheme.forest.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: const Icon(
                  Icons.volume_up_rounded,
                  color: AppTheme.forest,
                  size: 32,
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      alert.craftCategory ?? '',
                      style: AppTheme.titleLarge,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '↑ ${alert.pctChange ?? 0}% in ${alert.region ?? ''}',
                      style: AppTheme.bodyLarge.copyWith(
                        color: AppTheme.successGreen,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ),
              const Icon(Icons.play_circle_filled_rounded,
                  color: AppTheme.saffron, size: 44),
            ],
          ),
        ),
      ),
    );
  }
}
