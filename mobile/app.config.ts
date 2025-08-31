export default {
  android: {
    adaptiveIcon: {
      backgroundColor: '#ffffff',
      foregroundImage: './assets/adaptive-icon.png',
    },
  },
  assetBundlePatterns: ['**/*'],
  extra: {
    baseUrl: process.env.BASE_URL || 'http://192.168.100.35:8000/mobile',
  },
  icon: './assets/icon.png',
  ios: {
    supportsTablet: true,
  },
  name: 'demo',
  newArchEnabled: true,
  orientation: 'portrait',
  scheme: 'hyperview',
  slug: 'demo',
  splash: {
    backgroundColor: '#ffffff',
    image: './assets/splash.png',
    resizeMode: 'contain',
  },
  userInterfaceStyle: 'light',
  version: '1.0.0',
  web: {
    favicon: './assets/favicon.png',
  },
};
