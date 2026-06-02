import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

import zh from './locales/zh.json';
import en from './locales/en.json';

const STORAGE_KEY = 'superdhcp_lang';
const saved = localStorage.getItem(STORAGE_KEY);

// 检测浏览器语言偏好, 默认中文
const detectLang = (): string => {
  if (saved && ['zh', 'en'].includes(saved)) return saved;
  const navLang = navigator.language;
  return navLang.startsWith('zh') ? 'zh' : 'en';
};

i18n
  .use(initReactI18next)
  .init({
    resources: {
      zh: { translation: zh },
      en: { translation: en },
    },
    lng: detectLang(),
    fallbackLng: 'zh',
    debug: false,
    interpolation: {
      escapeValue: false,
    },
  });

// 语言切换工具函数
const langSwitch = (lang: string) => {
  i18n.changeLanguage(lang);
  localStorage.setItem(STORAGE_KEY, lang);
};

export { langSwitch };
export default i18n;