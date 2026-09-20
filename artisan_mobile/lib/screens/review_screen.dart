import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/artisan_provider.dart';
import '../services/audio_feedback_service.dart';
import '../theme/app_theme.dart';

/// Review screen showing:
///   - Raw vs. Studio photo slider comparison.
///   - Audio readout of extracted product details.
///   - Tactile [+100] / [-100] price adjuster.
///   - Large green "Publish to Marketplace" button.
class ReviewScreen extends StatefulWidget {
  const ReviewScreen({super.key});

  @override
  State<ReviewScreen> createState() => _ReviewScreenState();
}

class _ReviewScreenState extends State<ReviewScreen> {
  final _audio = AudioFeedbackService();
  double _sliderValue = 0.5; // 0 = raw, 1 = studio
  bool _isPublishing = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _audio.processingComplete();
    });
  }

  Future<void> _speakSummary(BuildContext context) async {
    final provider = context.read<ArtisanProvider>();
    final result = provider.lastIngestResult;
    if (result == null) return;

    await _audio.speakProductSummary(
      title: result.catalog.titleEn ?? 'Product',
      rawCost: result.catalog.rawCost ?? 0,
      sellingPrice: provider.adjustedPrice,
    );
  }

  Future<void> _publish(BuildContext context) async {
    final navigator = Navigator.of(context);
    final scaffoldMessenger = ScaffoldMessenger.of(context);
    setState(() => _isPublishing = true);
    final provider = context.read<ArtisanProvider>();
    final success = await provider.publishProduct();

    if (!mounted) return;

    setState(() => _isPublishing = false);

    if (success) {
      // Pop back to home
      navigator.popUntil((route) => route.isFirst);
    } else {
      scaffoldMessenger.showSnackBar(
        const SnackBar(
          content: Text('Publishing failed - please try again'),
          backgroundColor: AppTheme.dangerRed,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<ArtisanProvider>(
      builder: (context, provider, _) {
        final result = provider.lastIngestResult;

        if (result == null) {
          return Scaffold(
            appBar: AppBar(title: const Text('Review')),
            body: const Center(
              child: Text('No product data available', style: AppTheme.bodyLarge),
            ),
          );
        }

        final catalog = result.catalog;
        final pricing = result.pricing;

        return Scaffold(
          appBar: AppBar(title: const Text('Review Product')),
          body: SafeArea(
            child: SingleChildScrollView(
              padding: const EdgeInsets.only(bottom: 24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // ── Image comparison slider ────────────────────────
                  _ImageComparisonSlider(
                    rawBytes: provider.lastRawImageBytes,
                    studioBytes: result.studioImageBytes,
                    sliderValue: _sliderValue,
                    onChanged: (v) => setState(() => _sliderValue = v),
                  ),

                  const SizedBox(height: 16),

                  // ── Audio readout button ───────────────────────────
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    child: SizedBox(
                      height: AppTheme.minTouchHeight,
                      child: OutlinedButton.icon(
                        onPressed: () => _speakSummary(context),
                        icon: const Icon(Icons.volume_up_rounded, size: 28),
                        label: const Text('Hear Product Summary'),
                        style: OutlinedButton.styleFrom(
                          side: const BorderSide(color: AppTheme.forest, width: 2),
                          foregroundColor: AppTheme.forest,
                        ),
                      ),
                    ),
                  ),

                  const SizedBox(height: 20),

                  // ── Product details card ───────────────────────────
                  _ProductDetailsCard(
                    titleEn: catalog.titleEn ?? 'Handcrafted Product',
                    titleHi: catalog.titleHi ?? '',
                    craftType: catalog.craftType ?? '-',
                    material: catalog.material ?? '-',
                    rawCost: catalog.rawCost ?? 0,
                    laborDays: catalog.laborDays ?? 0,
                    transcript: result.rawTranscript,
                  ),

                  const SizedBox(height: 20),

                  // ── Price adjuster ─────────────────────────────────
                  _PriceAdjuster(
                    currentPrice: provider.adjustedPrice,
                    costFloor: pricing.costFloor,
                    minCorridor: pricing.minMarketCorridor,
                    maxCorridor: pricing.maxMarketCorridor,
                    margin: provider.adjustedPrice -
                        (catalog.rawCost ?? 0) -
                        (provider.adjustedPrice * 0.10),
                    onIncrement: () => provider.adjustPrice(100),
                    onDecrement: () => provider.adjustPrice(-100),
                  ),

                  const SizedBox(height: 28),

                  // ── Publish button ─────────────────────────────────
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    child: SizedBox(
                      height: 80,
                      child: ElevatedButton.icon(
                        onPressed: _isPublishing ? null : () => _publish(context),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppTheme.forest,
                          disabledBackgroundColor: AppTheme.forest.withOpacity(0.5),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(
                              AppTheme.borderRadiusLg,
                            ),
                          ),
                        ),
                        icon: _isPublishing
                            ? const SizedBox(
                                width: 28,
                                height: 28,
                                child: CircularProgressIndicator(
                                  strokeWidth: 3,
                                  color: Colors.white,
                                ),
                              )
                            : const Icon(Icons.storefront_rounded, size: 32),
                        label: Text(
                          _isPublishing ? 'Publishing...' : 'Publish to Marketplace',
                          style: const TextStyle(fontSize: 22),
                        ),
                      ),
                    ),
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

/// Interactive Raw vs Studio image comparison slider with real split-screen reveal.
class _ImageComparisonSlider extends StatelessWidget {
  final Uint8List? rawBytes;
  final Uint8List studioBytes;
  final double sliderValue;
  final ValueChanged<double> onChanged;

  const _ImageComparisonSlider({
    this.rawBytes,
    required this.studioBytes,
    required this.sliderValue,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        LayoutBuilder(
          builder: (context, constraints) {
            final width = constraints.maxWidth - 32;
            final splitX = (width * sliderValue.clamp(0.0, 1.0)).clamp(0.0, width);

            return Container(
              height: 320,
              margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(AppTheme.borderRadiusLg),
                color: Colors.grey.shade50,
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.08),
                    blurRadius: 16,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              clipBehavior: Clip.antiAlias,
              child: GestureDetector(
                onHorizontalDragUpdate: (details) {
                  final newRatio = (details.localPosition.dx / width).clamp(0.0, 1.0);
                  onChanged(newRatio);
                },
                child: Stack(
                  fit: StackFit.expand,
                  children: [
                    // Base layer: Raw photograph (or studio if raw unavailable)
                    if (rawBytes != null && rawBytes!.isNotEmpty)
                      Image.memory(
                        rawBytes!,
                        fit: BoxFit.contain,
                        errorBuilder: (_, __, ___) => const Center(
                          child: Icon(Icons.broken_image_rounded, size: 48),
                        ),
                      )
                    else
                      Image.memory(
                        studioBytes,
                        fit: BoxFit.contain,
                      ),

                    // Top layer: Studio photograph clipped to slider position
                    ClipRect(
                      clipper: _LeftSplitClipper(splitX),
                      child: Image.memory(
                        studioBytes,
                        fit: BoxFit.contain,
                      ),
                    ),

                    // Vertical divider line
                    Positioned(
                      left: splitX - 1.5,
                      top: 0,
                      bottom: 0,
                      child: Container(
                        width: 3,
                        decoration: BoxDecoration(
                          color: Colors.white,
                          boxShadow: [
                            BoxShadow(
                              color: Colors.black.withOpacity(0.35),
                              blurRadius: 4,
                            ),
                          ],
                        ),
                      ),
                    ),

                    // Circular center drag handle
                    Positioned(
                      left: splitX - 18,
                      top: 142,
                      child: Container(
                        width: 36,
                        height: 36,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: AppTheme.saffron,
                          border: Border.all(color: Colors.white, width: 2.5),
                          boxShadow: [
                            BoxShadow(
                              color: Colors.black.withOpacity(0.35),
                              blurRadius: 6,
                            ),
                          ],
                        ),
                        child: const Icon(
                          Icons.compare_arrows_rounded,
                          color: Colors.white,
                          size: 20,
                        ),
                      ),
                    ),

                    // Top labels
                    Positioned(
                      top: 12,
                      left: 12,
                      child: _ImageLabel(
                        label: 'Studio (AI)',
                        active: sliderValue > 0.3,
                      ),
                    ),
                    Positioned(
                      top: 12,
                      right: 12,
                      child: _ImageLabel(
                        label: 'Raw (Workshop)',
                        active: sliderValue < 0.7,
                      ),
                    ),
                  ],
                ),
              ),
            );
          },
        ),
        // Slider control below
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24),
          child: Row(
            children: [
              const Text('Raw', style: TextStyle(fontWeight: FontWeight.bold, color: AppTheme.slate)),
              const SizedBox(width: 8),
              Expanded(
                child: Slider(
                  value: sliderValue,
                  onChanged: onChanged,
                  activeColor: AppTheme.saffron,
                  inactiveColor: AppTheme.saffron.withOpacity(0.2),
                ),
              ),
              const SizedBox(width: 8),
              const Text('Studio', style: TextStyle(fontWeight: FontWeight.bold, color: AppTheme.saffron)),
            ],
          ),
        ),
      ],
    );
  }
}

class _LeftSplitClipper extends CustomClipper<Rect> {
  final double splitX;
  _LeftSplitClipper(this.splitX);

  @override
  Rect getClip(Size size) {
    return Rect.fromLTWH(0, 0, splitX, size.height);
  }

  @override
  bool shouldReclip(_LeftSplitClipper oldClipper) => oldClipper.splitX != splitX;
}

class _ImageLabel extends StatelessWidget {
  final String label;
  final bool active;

  const _ImageLabel({required this.label, required this.active});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: active
            ? AppTheme.saffron
            : Colors.black.withOpacity(0.4),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        label,
        style: const TextStyle(
          color: Colors.white,
          fontWeight: FontWeight.w700,
          fontSize: 13,
        ),
      ),
    );
  }
}

/// Extracted product detail cards.
class _ProductDetailsCard extends StatelessWidget {
  final String titleEn;
  final String titleHi;
  final String craftType;
  final String material;
  final double rawCost;
  final double laborDays;
  final String transcript;

  const _ProductDetailsCard({
    required this.titleEn,
    required this.titleHi,
    required this.craftType,
    required this.material,
    required this.rawCost,
    required this.laborDays,
    required this.transcript,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(titleEn, style: AppTheme.headlineMedium),
            if (titleHi.isNotEmpty) ...[
              const SizedBox(height: 4),
              Text(titleHi, style: AppTheme.titleLarge.copyWith(color: AppTheme.slate)),
            ],
            const Divider(height: 24),
            _DetailRow(icon: Icons.palette_rounded, label: 'Craft', value: craftType),
            _DetailRow(icon: Icons.texture_rounded, label: 'Material', value: material),
            _DetailRow(
              icon: Icons.attach_money_rounded,
              label: 'Raw Cost',
              value: '₹${rawCost.toInt()}',
            ),
            _DetailRow(
              icon: Icons.schedule_rounded,
              label: 'Labour',
              value: '${laborDays.toStringAsFixed(1)} days',
            ),
            const Divider(height: 24),
            const Text('Transcript', style: AppTheme.labelLarge),
            const SizedBox(height: 6),
            Text(
              transcript,
              style: AppTheme.bodyLarge.copyWith(fontStyle: FontStyle.italic),
              maxLines: 4,
              overflow: TextOverflow.ellipsis,
            ),
          ],
        ),
      ),
    );
  }
}

class _DetailRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;

  const _DetailRow({
    required this.icon,
    required this.label,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          Icon(icon, size: 22, color: AppTheme.saffron),
          const SizedBox(width: 10),
          Text('$label: ', style: AppTheme.labelLarge),
          Expanded(child: Text(value, style: AppTheme.bodyBold)),
        ],
      ),
    );
  }
}

/// Massive [+100] / [-100] tactile price adjuster.
class _PriceAdjuster extends StatelessWidget {
  final double currentPrice;
  final double costFloor;
  final double minCorridor;
  final double maxCorridor;
  final double margin;
  final VoidCallback onIncrement;
  final VoidCallback onDecrement;

  const _PriceAdjuster({
    required this.currentPrice,
    required this.costFloor,
    required this.minCorridor,
    required this.maxCorridor,
    required this.margin,
    required this.onIncrement,
    required this.onDecrement,
  });

  @override
  Widget build(BuildContext context) {
    final priceInRange =
        currentPrice >= minCorridor && currentPrice <= maxCorridor;

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            const Text('Selling Price', style: AppTheme.titleLarge),
            const SizedBox(height: 12),
            // Price display
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                // Minus button
                _BigRoundButton(
                  icon: Icons.remove_rounded,
                  color: AppTheme.dangerRed,
                  onTap: onDecrement,
                ),
                const SizedBox(width: 24),
                // Current price
                Column(
                  children: [
                    Text(
                      '₹${currentPrice.toInt()}',
                      style: TextStyle(
                        fontSize: 44,
                        fontWeight: FontWeight.w800,
                        color: priceInRange
                            ? AppTheme.charcoal
                            : AppTheme.dangerRed,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 10,
                        vertical: 4,
                      ),
                      decoration: BoxDecoration(
                        color: priceInRange
                            ? AppTheme.successGreen.withOpacity(0.1)
                            : AppTheme.dangerRed.withOpacity(0.1),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        priceInRange ? 'Fair Price Range' : 'Outside Range',
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                          color: priceInRange
                              ? AppTheme.successGreen
                              : AppTheme.dangerRed,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(width: 24),
                // Plus button
                _BigRoundButton(
                  icon: Icons.add_rounded,
                  color: AppTheme.forest,
                  onTap: onIncrement,
                ),
              ],
            ),
            const SizedBox(height: 16),
            // Corridor info
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                _SmallInfo(label: 'Floor', value: '₹${costFloor.toInt()}'),
                _SmallInfo(label: 'Min', value: '₹${minCorridor.toInt()}'),
                _SmallInfo(label: 'Max', value: '₹${maxCorridor.toInt()}'),
                _SmallInfo(
                  label: 'Margin',
                  value: '₹${margin.toInt()}',
                  color: margin > 0 ? AppTheme.successGreen : AppTheme.dangerRed,
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _BigRoundButton extends StatelessWidget {
  final IconData icon;
  final Color color;
  final VoidCallback onTap;

  const _BigRoundButton({
    required this.icon,
    required this.color,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      color: color,
      shape: const CircleBorder(),
      elevation: 3,
      child: InkWell(
        customBorder: const CircleBorder(),
        onTap: onTap,
        child: SizedBox(
          width: 72,
          height: 72,
          child: Icon(icon, color: Colors.white, size: 40),
        ),
      ),
    );
  }
}

class _SmallInfo extends StatelessWidget {
  final String label;
  final String value;
  final Color? color;

  const _SmallInfo({required this.label, required this.value, this.color});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(label, style: AppTheme.labelLarge),
        const SizedBox(height: 2),
        Text(
          value,
          style: AppTheme.bodyBold.copyWith(color: color ?? AppTheme.charcoal),
        ),
      ],
    );
  }
}
