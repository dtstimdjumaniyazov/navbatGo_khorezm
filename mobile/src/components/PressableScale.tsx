import React from 'react';
import { Pressable, PressableProps, StyleProp, ViewStyle } from 'react-native';

interface Props extends Omit<PressableProps, 'style'> {
  style?: StyleProp<ViewStyle>;
  children?: React.ReactNode;
}

/**
 * Pressable с эффектом нажатия (scale 0.98 + лёгкое затемнение) —
 * RN-аналог css `transition-all active:scale-[0.98]`.
 */
export const PressableScale: React.FC<Props> = ({ style, children, ...rest }) => (
  <Pressable
    {...rest}
    style={({ pressed }) => [
      style,
      pressed && { transform: [{ scale: 0.98 }], opacity: 0.9 },
    ]}
  >
    {children}
  </Pressable>
);
