import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/models.dart';
import '../providers/artisan_provider.dart';
import '../services/audio_feedback_service.dart';
import '../theme/app_theme.dart';

/// Displays incoming cluster order shares (RFQ allocations) with
/// a large green "Accept Share" button per order and an audio prompt.
class OrdersScreen extends StatefulWidget {
  const OrdersScreen({super.key});

  @override
  State<OrdersScreen> createState() => _OrdersScreenState();
}

class _OrdersScreenState extends State<OrdersScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<ArtisanProvider>().loadOrders();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<ArtisanProvider>(
      builder: (context, provider, _) {
        final orders = provider.orders;

        return Scaffold(
          appBar: AppBar(title: const Text('My Orders')),
          body: SafeArea(
            child: orders.isEmpty
                ? const _EmptyState()
                : ListView.builder(
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    itemCount: orders.length,
                    itemBuilder: (context, index) {
                      return _OrderCard(order: orders[index]);
                    },
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

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.inbox_rounded,
            size: 80,
            color: AppTheme.slate.withOpacity(0.3),
          ),
          const SizedBox(height: 16),
          const Text(
            'No orders yet',
            style: AppTheme.headlineMedium,
          ),
          const SizedBox(height: 8),
          const Text(
            'New orders from buyers will appear here',
            style: AppTheme.bodyLarge,
          ),
        ],
      ),
    );
  }
}

/// A single order share card with buyer name, units, payout, and
/// a large Accept button.
class _OrderCard extends StatefulWidget {
  final OrderShare order;

  const _OrderCard({required this.order});

  @override
  State<_OrderCard> createState() => _OrderCardState();
}

class _OrderCardState extends State<_OrderCard> {
  final _audio = AudioFeedbackService();
  bool _accepted = false;

  Future<void> _acceptOrder() async {
    setState(() => _accepted = true);
    await _audio.speak(
      'ऑर्डर स्वीकार किया गया। '
      '${widget.order.allocatedUnits} इकाइयाँ, '
      '₹${widget.order.payoutAmount.toInt()} भुगतान।',
    );
  }

  @override
  Widget build(BuildContext context) {
    final order = widget.order;

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Buyer name & status
            Row(
              children: [
                Container(
                  width: 48,
                  height: 48,
                  decoration: BoxDecoration(
                    color: AppTheme.forest.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Icon(
                    Icons.business_rounded,
                    color: AppTheme.forest,
                    size: 26,
                  ),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(order.buyerName, style: AppTheme.titleLarge),
                      const SizedBox(height: 4),
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 8,
                          vertical: 3,
                        ),
                        decoration: BoxDecoration(
                          color: _accepted
                              ? AppTheme.successGreen.withOpacity(0.1)
                              : AppTheme.saffron.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Text(
                          _accepted ? 'Accepted' : order.status,
                          style: TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w700,
                            color: _accepted
                                ? AppTheme.successGreen
                                : AppTheme.saffron,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const Divider(height: 28),
            // Units & payout
            Row(
              children: [
                Expanded(
                  child: _InfoBlock(
                    icon: Icons.inventory_2_rounded,
                    label: 'Your Share',
                    value: '${order.allocatedUnits} units',
                  ),
                ),
                Container(width: 1, height: 40, color: Colors.grey.shade300),
                Expanded(
                  child: _InfoBlock(
                    icon: Icons.payments_rounded,
                    label: 'Payout',
                    value: '₹${order.payoutAmount.toInt()}',
                    valueColor: AppTheme.forest,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 18),
            // Accept button
            if (!_accepted)
              SizedBox(
                height: AppTheme.bigButtonHeight,
                width: double.infinity,
                child: ElevatedButton.icon(
                  onPressed: _acceptOrder,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.forest,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(
                        AppTheme.borderRadiusMd,
                      ),
                    ),
                  ),
                  icon: const Icon(Icons.check_circle_rounded, size: 28),
                  label: const Text(
                    'Accept Share',
                    style: TextStyle(fontSize: 20),
                  ),
                ),
              )
            else
              SizedBox(
                height: AppTheme.bigButtonHeight,
                width: double.infinity,
                child: OutlinedButton.icon(
                  onPressed: null,
                  style: OutlinedButton.styleFrom(
                    side: const BorderSide(color: AppTheme.successGreen, width: 2),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(
                        AppTheme.borderRadiusMd,
                      ),
                    ),
                  ),
                  icon: const Icon(
                    Icons.check_circle_rounded,
                    size: 28,
                    color: AppTheme.successGreen,
                  ),
                  label: const Text(
                    'Order Accepted',
                    style: TextStyle(
                      fontSize: 20,
                      color: AppTheme.successGreen,
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _InfoBlock extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final Color? valueColor;

  const _InfoBlock({
    required this.icon,
    required this.label,
    required this.value,
    this.valueColor,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Icon(icon, color: AppTheme.slate, size: 22),
        const SizedBox(height: 6),
        Text(label, style: AppTheme.labelLarge),
        const SizedBox(height: 4),
        Text(
          value,
          style: AppTheme.bodyBold.copyWith(
            fontSize: 18,
            color: valueColor ?? AppTheme.charcoal,
          ),
        ),
      ],
    );
  }
}
