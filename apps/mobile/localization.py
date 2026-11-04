"""Translate only source-owned error messages. Never translate routine data."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]/'localization'
CATALOG={p.stem:json.loads(p.read_text()) for p in ROOT.glob('*.json') if p.stem!='registry'}
LANGUAGES=json.loads((ROOT/'registry.json').read_text())
def normalize(language):return language if language in LANGUAGES else 'en'
def translate(key,language='en'):
    return CATALOG.get(language,CATALOG['en']).get(key,CATALOG['en'].get(key,key))
