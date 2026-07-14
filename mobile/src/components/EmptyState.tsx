import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { colors, radius } from '../theme';

interface Props {
  icon: React.ReactNode;
  message: string;
}

/** Единый стиль пустых состояний: мягкая тень и голубой акцент вместо плоской серой рамки. */
export const EmptyState: React.FC<Props> = ({ icon, message }) => (
  <View style={styles.box}>
    <View style={styles.iconCircle}>{icon}</View>
    <Text style={styles.message}>{message}</Text>
  </View>
);

const styles = StyleSheet.create({
  box: {
    backgroundColor: colors.inProgressBg,
    borderRadius: radius + 4,
    paddingVertical: 28,
    paddingHorizontal: 16,
    alignItems: 'center',
    gap: 8,
    shadowColor: colors.primary,
    shadowOpacity: 0.08,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 2 },
    elevation: 1,
  },
  iconCircle: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#fff',
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOpacity: 0.08,
    shadowRadius: 4,
    shadowOffset: { width: 0, height: 1 },
    elevation: 1,
  },
  message: { color: colors.muted, fontSize: 13, textAlign: 'center' },
});
