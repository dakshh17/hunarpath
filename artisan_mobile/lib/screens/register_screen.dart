import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/artisan_provider.dart';
import '../services/api_client.dart';
import 'home_screen.dart';

class RegisterScreen extends StatefulWidget {
  const RegisterScreen({super.key});

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  final _nameController = TextEditingController();
  final _phoneController = TextEditingController();
  final _pinController = TextEditingController();
  final _confirmPinController = TextEditingController();
  
  String? _selectedCluster;
  String _selectedDialect = 'hi';
  bool _isLoading = false;
  String? _error;
  List<Map<String, dynamic>> _clusters = [];

  @override
  void initState() {
    super.initState();
    _loadClusters();
  }

  Future<void> _loadClusters() async {
    try {
      final res = await ApiClient().fetchClustersGeoJSON();
      final features = res['features'] as List;
      setState(() {
        _clusters = features.map((f) {
          final props = f['properties'] as Map<String, dynamic>;
          return {
            'id': props['id']?.toString() ?? '1',
            'name': props['name']?.toString() ?? 'Cluster',
          };
        }).toList();
        if (_clusters.isNotEmpty) {
          _selectedCluster = _clusters.first['id'] as String;
        }
      });
    } catch (e) {
      // Fallback
      setState(() {
        _clusters = [
          {'id': '1', 'name': 'Varanasi Weavers'},
          {'id': '2', 'name': 'Bastar Bell Metal'},
        ];
        _selectedCluster = '1';
      });
    }
  }

  void _register() async {
    if (_pinController.text != _confirmPinController.text) {
      setState(() => _error = 'PINs do not match');
      return;
    }

    setState(() {
      _isLoading = true;
      _error = null;
    });

    final provider = Provider.of<ArtisanProvider>(context, listen: false);
    String phone = _phoneController.text.trim();
    if (!phone.startsWith('+')) {
      phone = '+91$phone';
    }
    final success = await provider.register(
      name: _nameController.text.trim(),
      phone: phone,
      pin: _pinController.text.trim(),
      clusterId: _selectedCluster ?? '1',
      dialect: _selectedDialect,
    );

    if (!mounted) return;

    if (success) {
      Navigator.pushAndRemoveUntil(
        context,
        MaterialPageRoute(builder: (_) => const HomeScreen()),
        (route) => false,
      );
    } else {
      setState(() {
        _isLoading = false;
        _error = provider.authError ?? 'Registration failed';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Register')),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (_error != null)
                Padding(
                  padding: const EdgeInsets.only(bottom: 16.0),
                  child: Text(
                    _error!,
                    style: const TextStyle(color: Colors.red),
                    textAlign: TextAlign.center,
                  ),
                ),
              TextField(
                controller: _nameController,
                decoration: const InputDecoration(labelText: 'Name', border: OutlineInputBorder()),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _phoneController,
                decoration: const InputDecoration(labelText: 'Phone', prefixText: '+91 ', border: OutlineInputBorder()),
                keyboardType: TextInputType.phone,
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _pinController,
                decoration: const InputDecoration(labelText: '4-digit PIN', border: OutlineInputBorder()),
                keyboardType: TextInputType.number,
                obscureText: true,
                maxLength: 4,
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _confirmPinController,
                decoration: const InputDecoration(labelText: 'Confirm PIN', border: OutlineInputBorder()),
                keyboardType: TextInputType.number,
                obscureText: true,
                maxLength: 4,
              ),
              const SizedBox(height: 16),
              DropdownButtonFormField<String>(
                value: _selectedCluster,
                decoration: const InputDecoration(labelText: 'Cluster', border: OutlineInputBorder()),
                items: _clusters.map((c) {
                  return DropdownMenuItem<String>(
                    value: c['id'] as String,
                    child: Text(c['name'] as String),
                  );
                }).toList(),
                onChanged: (val) {
                  setState(() => _selectedCluster = val);
                },
              ),
              const SizedBox(height: 16),
              DropdownButtonFormField<String>(
                value: _selectedDialect,
                decoration: const InputDecoration(labelText: 'Dialect', border: OutlineInputBorder()),
                items: const [
                  DropdownMenuItem(value: 'hi', child: Text('Hindi')),
                  DropdownMenuItem(value: 'gu', child: Text('Gujarati')),
                  DropdownMenuItem(value: 'bn', child: Text('Bengali')),
                ],
                onChanged: (val) {
                  if (val != null) setState(() => _selectedDialect = val);
                },
              ),
              const SizedBox(height: 24),
              ElevatedButton(
                onPressed: _isLoading ? null : _register,
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFFFF6B00),
                  padding: const EdgeInsets.symmetric(vertical: 16),
                ),
                child: _isLoading
                    ? const CircularProgressIndicator(color: Colors.white)
                    : const Text('Register', style: TextStyle(fontSize: 18, color: Colors.white)),
              ),
              const SizedBox(height: 16),
              TextButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('Already registered? Login', style: TextStyle(color: Color(0xFFFF6B00))),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
