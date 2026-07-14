// lucide-react-native публикует чистый ESM (package.json "exports" на .mjs).
// Metro в связке с этим пакетом уходит в циклический/битый разбор импортов
// (см. lucide-icons/lucide#2299) — отключаем unstable_enablePackageExports,
// чтобы Metro брал CJS-сборку через "main", а не "exports".
const { getDefaultConfig } = require('expo/metro-config');

const config = getDefaultConfig(__dirname);
config.resolver.unstable_enablePackageExports = false;

module.exports = config;
