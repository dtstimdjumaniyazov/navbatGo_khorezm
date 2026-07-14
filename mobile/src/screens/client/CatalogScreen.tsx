import { Store } from 'lucide-react-native';
import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Image,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { api, ApiError } from '../../api/client';
import { EmptyState } from '../../components/EmptyState';
import { PressableScale } from '../../components/PressableScale';
import { Lang, locText, t } from '../../i18n';
import { cardShadow, colors, radius } from '../../theme';
import { PublicPoint } from '../../types';

interface Props {
  lang: Lang;
  onSelect: (point: PublicPoint) => void;
}

/** Каталог автосервисов — стартовый экран клиента. */
export const CatalogScreen: React.FC<Props> = ({ lang, onSelect }) => {
  const [points, setPoints] = useState<PublicPoint[] | null>(null);
  const [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      setPoints(await api.getPublicPoints());
      setError('');
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t(lang, 'no_connection'));
    }
  }, [lang]);

  useEffect(() => {
    load();
  }, [load]);

  if (points === null) {
    return (
      <View style={styles.center}>
        {error ? (
          <>
            <Text style={styles.error}>{error}</Text>
            <Pressable style={styles.retryBtn} onPress={load}>
              <Text style={styles.retryText}>{t(lang, 'retry')}</Text>
            </Pressable>
          </>
        ) : (
          <ActivityIndicator color={colors.primary} size="large" />
        )}
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={async () => {
            setRefreshing(true);
            await load();
            setRefreshing(false);
          }}
        />
      }
    >
      <Text style={styles.title}>{t(lang, 'catalog_title')}</Text>
      {points.length === 0 && (
        <EmptyState icon={<Store size={18} color={colors.primary} />} message={t(lang, 'no_points')} />
      )}
      {points.map((p) => {
        const photo = p.media.find((m) => m.media_type === 'photo' && m.image);
        return (
          <PressableScale key={p.id} style={styles.cardShadowWrap} onPress={() => onSelect(p)}>
            {/* Тень — на внешнем View: overflow:hidden внутри (нужен для
                обрезки фото по скруглению) иначе бы гасил тень целиком */}
            <View style={styles.card}>
              {photo?.image ? (
                <Image source={{ uri: photo.image }} style={styles.photo} />
              ) : (
                <View style={[styles.photo, styles.photoStub]}>
                  <Text style={styles.photoStubText}>🔧</Text>
                </View>
              )}
              <View style={styles.cardBody}>
                <Text style={styles.name}>{p.name}</Text>
                {!!p.address && (
                  <Text style={styles.address}>
                    📍 {locText(lang, p.address, p.address_uz)}
                  </Text>
                )}
                {!!p.description && (
                  <Text style={styles.desc} numberOfLines={2}>
                    {locText(lang, p.description, p.description_uz)}
                  </Text>
                )}
                <Text style={styles.services}>
                  {t(lang, 'services_count', { n: p.services.length })} ·{' '}
                  {p.work_start.slice(0, 5)}–{p.work_end.slice(0, 5)}
                </Text>
              </View>
            </View>
          </PressableScale>
        );
      })}
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  content: { padding: 16, gap: 12, paddingBottom: 32 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24, gap: 16 },
  title: { fontSize: 22, fontWeight: '800', color: colors.text },
  error: { color: colors.danger, textAlign: 'center' },
  retryBtn: {
    backgroundColor: colors.primary,
    paddingVertical: 12,
    paddingHorizontal: 28,
    borderRadius: radius,
  },
  retryText: { color: '#fff', fontWeight: '700' },
  cardShadowWrap: { borderRadius: radius, ...cardShadow },
  card: {
    backgroundColor: colors.card,
    borderRadius: radius,
    borderWidth: 1,
    borderColor: colors.border,
    overflow: 'hidden',
  },
  photo: { width: '100%', height: 140 },
  photoStub: { backgroundColor: '#dbeafe', alignItems: 'center', justifyContent: 'center' },
  photoStubText: { fontSize: 42 },
  cardBody: { padding: 12, gap: 4 },
  name: { fontSize: 17, fontWeight: '800', color: colors.text },
  address: { color: colors.muted, fontSize: 13 },
  desc: { color: colors.text, fontSize: 13, lineHeight: 18 },
  services: { color: colors.primary, fontSize: 13, fontWeight: '600', marginTop: 2 },
});
