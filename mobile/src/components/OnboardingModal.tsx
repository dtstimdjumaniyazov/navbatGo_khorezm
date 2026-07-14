import React from 'react';
import { Modal, Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, radius } from '../theme';

interface Step {
  icon: React.ReactNode;
  title: string;
  text: string;
}

interface Props {
  visible: boolean;
  onClose: () => void;
  heading: string;
  steps: Step[];
  ctaLabel: string;
}

/** Короткая инструкция «как это работает» — один раз при первом входе. */
export const OnboardingModal: React.FC<Props> = ({ visible, onClose, heading, steps, ctaLabel }) => (
  <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
    <View style={styles.backdrop}>
      <Pressable style={StyleSheet.absoluteFill} onPress={onClose} />
      <View style={styles.card}>
        <Text style={styles.heading}>{heading}</Text>
        <View style={styles.steps}>
          {steps.map((s, i) => (
            <View key={i} style={styles.step}>
              <View style={styles.iconWrap}>{s.icon}</View>
              <View style={styles.stepText}>
                <Text style={styles.stepTitle}>{s.title}</Text>
                <Text style={styles.stepBody}>{s.text}</Text>
              </View>
            </View>
          ))}
        </View>
        <Pressable style={styles.cta} onPress={onClose}>
          <Text style={styles.ctaText}>{ctaLabel}</Text>
        </Pressable>
      </View>
    </View>
  </Modal>
);

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.4)',
    justifyContent: 'center',
    padding: 20,
  },
  card: {
    backgroundColor: colors.card,
    borderRadius: radius + 4,
    padding: 20,
    gap: 16,
  },
  heading: { fontSize: 18, fontWeight: '800', color: colors.text },
  steps: { gap: 14 },
  step: { flexDirection: 'row', alignItems: 'flex-start', gap: 12 },
  iconWrap: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.inProgressBg,
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepText: { flex: 1 },
  stepTitle: { fontSize: 14, fontWeight: '700', color: colors.text },
  stepBody: { fontSize: 13, color: colors.muted, marginTop: 2, lineHeight: 18 },
  cta: {
    backgroundColor: colors.primary,
    borderRadius: radius,
    paddingVertical: 13,
    alignItems: 'center',
  },
  ctaText: { color: '#fff', fontWeight: '700', fontSize: 15 },
});
