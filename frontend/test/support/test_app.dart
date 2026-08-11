import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

Widget testApp({
  required Widget home,
  ThemeData? theme,
  TransitionBuilder? builder,
}) => ProviderScope(
  child: MaterialApp(home: home, theme: theme, builder: builder),
);
