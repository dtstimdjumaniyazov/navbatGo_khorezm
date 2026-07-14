/**
 * Push-уведомления через Expo. Работают только на реальном устройстве и в
 * dev/production-сборке (не в Expo Go на Android начиная с SDK 53) — при
 * недоступности возвращаем понятную ошибку вместо падения.
 */
import Constants from 'expo-constants';
import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

export interface PushRegistration {
  token: string | null;
  error: string | null;
}

/** Запросить разрешение (если ещё не спрашивали) и получить Expo push-токен устройства. */
export async function registerForPushToken(): Promise<PushRegistration> {
  if (!Device.isDevice) {
    return { token: null, error: 'Push работает только на реальном устройстве, не в симуляторе.' };
  }

  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('default', {
      name: 'default',
      importance: Notifications.AndroidImportance.DEFAULT,
    });
  }

  const { status: existing } = await Notifications.getPermissionsAsync();
  let finalStatus = existing;
  if (existing !== 'granted') {
    const { status } = await Notifications.requestPermissionsAsync();
    finalStatus = status;
  }
  if (finalStatus !== 'granted') {
    return { token: null, error: 'Уведомления не разрешены в настройках телефона.' };
  }

  try {
    const projectId =
      Constants.expoConfig?.extra?.eas?.projectId ?? Constants.easConfig?.projectId;
    const { data } = await Notifications.getExpoPushTokenAsync(
      projectId ? { projectId } : undefined,
    );
    return { token: data, error: null };
  } catch (e) {
    return {
      token: null,
      error: e instanceof Error ? e.message : 'Не удалось получить push-токен.',
    };
  }
}
