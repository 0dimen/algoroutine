import {messages,languages} from '/messages.js';
export {languages};
export const supportedLanguages=Object.keys(languages);
export function normalizeLanguage(value){return supportedLanguages.includes(value)?value:'en';}
export function locale(){try{return normalizeLanguage(localStorage.getItem('routine.language'));}catch{return 'en';}}
export function setLocale(value){localStorage.setItem('routine.language',normalizeLanguage(value));document.documentElement.lang=locale();document.documentElement.dir=languages[locale()].direction;}
// Only source-owned UI msgids enter t(). User text is passed through untouched.
export function t(key,values={}){let text=messages[locale()]?.[key]??messages.en[key]??key;for(const [k,v]of Object.entries(values))text=text.replaceAll('{'+k+'}',String(v));return text;}
export function stepCount(n){const category=new Intl.PluralRules(locale()).select(n);return t(messages[locale()]['steps.'+category]?'steps.'+category:'steps.other',{count:n});}
