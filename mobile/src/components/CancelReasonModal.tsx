import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { Lang, t } from '../i18n';
import { colors, radius } from '../theme';

interface Props {
  visible: boolean;
  lang: Lang;
  onClose: () => void;
  /** Отправка отмены; при ошибке кидает исключение — модалка покажет его и останется открытой */
  onConfirm: (reason: string) => Promise<void>;
}

/** Причина обязательна — уходит клиенту в Telegram-уведомлении об отмене. */
export const CancelReasonModal: React.FC<Props> = ({ visible, lang, onClose, onConfirm }) => {
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (visible) {
      setReason('');
      setError('');
    }
  }, [visible]);

  const submit = async () => {
    if (!reason.trim()) {
      setError(t(lang, 'm_cancel_reason_required'));
      return;
    }
    setSubmitting(true);
    setError('');
    try {
      await onConfirm(reason.trim());
    } catch (e) {
      setError(e instanceof Error ? e.message : t(lang, 'm_cancel_reason_failed'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <KeyboardAvoidingView
        style={styles.backdrop}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <Pressable style={StyleSheet.absoluteFill} onPress={onClose} />
        <View style={styles.card}>
          <Text style={styles.title}>{t(lang, 'm_cancel_reason_title')}</Text>
          <Text style={styles.label}>{t(lang, 'm_cancel_reason_label')}</Text>
          <TextInput
            style={styles.input}
            value={reason}
            onChangeText={setReason}
            placeholder={t(lang, 'm_cancel_reason_placeholder')}
            placeholderTextColor={colors.muted}
            multiline
            autoFocus
          />
          {!!error && <Text style={styles.error}>{error}</Text>}
          <View style={styles.row}>
            <Pressable style={styles.backBtn} onPress={onClose} disabled={submitting}>
              <Text style={styles.backText}>{t(lang, 'm_cancel_reason_back')}</Text>
            </Pressable>
            <Pressable
              style={[styles.confirmBtn, submitting && styles.busy]}
              onPress={submit}
              disabled={submitting}
            >
              {submitting ? (
                <ActivityIndicator color="#fff" size="small" />
              ) : (
                <Text style={styles.confirmText}>{t(lang, 'm_cancel_reason_confirm')}</Text>
              )}
            </Pressable>
          </View>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
};

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.4)',
    justifyContent: 'center',
    padding: 20,
  },
  card: {
    backgroundColor: colors.card,
    borderRadius: radius,
    padding: 18,
    gap: 10,
  },
  title: { fontSize: 17, fontWeight: '800', color: colors.text },
  label: { fontSize: 13, color: colors.muted },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 10,
    padding: 10,
    minHeight: 80,
    textAlignVertical: 'top',
    fontSize: 15,
    color: colors.text,
  },
  error: { color: colors.danger, fontSize: 13 },
  row: { flexDirection: 'row', gap: 8, marginTop: 4 },
  backBtn: { flex: 1, paddingVertical: 12, alignItems: 'center', borderRadius: radius },
  backText: { color: colors.muted, fontWeight: '700', fontSize: 15 },
  confirmBtn: {
    flex: 1,
    paddingVertical: 12,
    alignItems: 'center',
    borderRadius: radius,
    backgroundColor: colors.danger,
  },
  busy: { opacity: 0.6 },
  confirmText: { color: '#fff', fontWeight: '700', fontSize: 15 },
});
