import { ChevronDown } from 'lucide-react-native';
import React, { useState } from 'react';
import { LayoutAnimation, Pressable, StyleSheet, Text, View } from 'react-native';

import { cardShadow, colors, radius } from '../theme';

interface Props {
  title: string;
  icon: React.ReactNode;
  defaultOpen?: boolean;
  children: React.ReactNode;
}

/** Сворачиваемая карточка витрины: заголовок с иконкой + шеврон, контент по тапу. */
export const Section: React.FC<Props> = ({ title, icon, defaultOpen, children }) => {
  const [open, setOpen] = useState(!!defaultOpen);

  const toggle = () => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setOpen((o) => !o);
  };

  return (
    // Тень — на внешнем View: overflow:hidden внутри (нужен, чтобы прижать
    // ripple-эффект Android к скруглённым углам) иначе бы гасил тень целиком
    <View style={styles.shadowWrap}>
      <View style={styles.card}>
        <Pressable onPress={toggle} style={styles.header}>
          <View style={styles.titleRow}>
            {icon}
            <Text style={styles.title}>{title}</Text>
          </View>
          <ChevronDown
            size={20}
            color={colors.muted}
            style={open ? styles.chevronOpen : undefined}
          />
        </Pressable>
        {open && <View style={styles.body}>{children}</View>}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  shadowWrap: { borderRadius: radius, ...cardShadow },
  card: {
    backgroundColor: colors.card,
    borderRadius: radius,
    borderWidth: 1,
    borderColor: colors.border,
    overflow: 'hidden',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 14,
    paddingHorizontal: 14,
  },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  title: { fontSize: 15, fontWeight: '800', color: colors.text },
  chevronOpen: { transform: [{ rotate: '180deg' }] },
  body: { paddingHorizontal: 14, paddingBottom: 14, gap: 10 },
});
