import pandas as pd
import logging
from django.db import transaction
from core.models import Yosh, Mahalla
from .models import UnemployedYouth, ResponsibleLeader
from datetime import datetime

logger = logging.getLogger(__name__)

def normalize_string(s):
    """Normalize string for consistent comparison"""
    if not s or s == 'nan':
        return ''
    # Remove apostrophes, dots, dashes, and spaces, then lowercase
    for char in ["'", "ʻ", "’", "‘", ".", "-", " ", "\n", "\t"]:
        s = s.replace(char, "")
    return s.lower()

def import_unemployed_youth_from_excel(file_path):
    """
    Import unemployed youth from 'ishsiz yoshlar 2026.xlsx' (Royxat sheet).
    
    Logic:
    1. Read data from 'Royxat' sheet
    2. For each youth:
       - Check if exists in Yosh table by JSHSHIR
       - If not exists, create in Yosh table first
       - Match mahalla by name (normalized)
       - Then add to UnemployedYouth table
    
    Returns: (imported_count, created_yosh_count, errors)
    """
    try:
        df = pd.read_excel(file_path, sheet_name='Royxat', header=1)
        logger.info(f"Excel file loaded successfully with {len(df)} rows")
    except FileNotFoundError as e:
        logger.error(f"Excel file not found: {file_path}")
        return 0, 0, [f"Excel faylni topib bo'lmadi: {str(e)}"]
    except Exception as e:
        logger.error(f"Error reading Excel file: {str(e)}")
        return 0, 0, [f"Excel faylni o'qishda xato: {str(e)}"]
    
    imported_count = 0
    created_yosh_count = 0
    errors = []
    
    # Pre-load mahallas for faster lookup
    all_mahallas = list(Mahalla.objects.all())
    mahalla_map = {normalize_string(m.name): m for m in all_mahallas}
    
    # Column mapping (Royxat sheet structure)
    COL_FIO = 'Ф.И.О.'
    COL_BIRTH_YEAR = ' '  # Year column
    COL_PASSPORT = 'Паспорт (туғилганлик гувоҳномаси) серияси ва рақами'
    COL_JSHSHIR = 'ЖШШИР'
    COL_BIRTH_DATE = 'Туғилган санаси'
    COL_PHONE = 'Тел рақами'
    COL_MAHALLA = 'Маҳалла номи'
    COL_CATEGORY = 'Тоифаси'
    COL_LEADER_POSITION = 'Бириктирилган масъуллар lavozimi'
    COL_LEADER_FIO = 'Бириктирилган масъуллар FIOsi'
    COL_LEADER_LEVEL = 'Даражаси'
    
    for index, row in df.iterrows():
        try:
            # Extract data
            fullname = str(row.get(COL_FIO, '')).strip()
            jshshir = str(row.get(COL_JSHSHIR, '')).strip()
            passport = str(row.get(COL_PASSPORT, '')).strip()
            birth_year = row.get(COL_BIRTH_YEAR)
            birth_date_raw = row.get(COL_BIRTH_DATE)
            phone = str(row.get(COL_PHONE, '')).strip()
            mahalla_name = str(row.get(COL_MAHALLA, '')).strip()
            category_text = str(row.get(COL_CATEGORY, '')).strip()
            leader_position = str(row.get(COL_LEADER_POSITION, '')).strip()
            leader_fio = str(row.get(COL_LEADER_FIO, '')).strip()
            leader_level = str(row.get(COL_LEADER_LEVEL, '')).strip()
            
            # Skip empty rows
            if not fullname or fullname == 'nan' or not jshshir or jshshir == 'nan' or jshshir == '..':
                continue
            
            # Sanitize jshshir (sometimes excel reads as float)
            if 'e+' in jshshir.lower():
                jshshir = str(int(float(jshshir)))
            elif '.' in jshshir:
                jshshir = jshshir.split('.')[0]
            
            if len(jshshir) < 14:
                jshshir = jshshir.zfill(14)
            
            with transaction.atomic():
                # 1. Find mahalla using normalized comparison
                norm_mahalla = normalize_string(mahalla_name)
                mahalla = mahalla_map.get(norm_mahalla)
                
                # If still not found, try icontains manually or some specific mappings
                if not mahalla:
                    # Manual mapping for common misspellings or variations
                    manual_map = {
                        'ggulom': 'ggofur',
                        'bogiiram': 'bogieram',
                        'buyuksiymo': 'buyuksimo',
                        'jmanguberdi': 'jaloladdinmanguberdi',
                        'muhomon': 'muxomon',
                        'shavot': 'shovot',
                        'yuqorishavot': 'yuqorishovot',
                        'pahlavonmahmud': 'paxlavonmaxmud',
                        'qirtepa': 'kirtepa',
                        'sulaymonqala': 'sulaymonqalaasi',
                        'oybek': 'oybeknomli',
                        'yangihayot': 'yangixayot',
                    }
                    mapped_name = manual_map.get(norm_mahalla)
                    if mapped_name:
                        mahalla = mahalla_map.get(mapped_name)

                if not mahalla:
                    errors.append(f"Qator {index + 3}: Mahalla '{mahalla_name}' topilmadi - {fullname}")
                    continue
                
                # 2. Check if Yosh exists by JSHSHIR
                yosh = Yosh.objects.filter(jshshir=jshshir).first()
                
                if not yosh:
                    # Create new Yosh record
                    try:
                        # Parse birth date
                        birth_date = None
                        if pd.notna(birth_date_raw):
                            if isinstance(birth_date_raw, pd.Timestamp):
                                birth_date = birth_date_raw.date()
                            elif isinstance(birth_date_raw, str):
                                try:
                                    birth_date = pd.to_datetime(birth_date_raw).date()
                                except:
                                    pass
                        
                        # Use year if date is missing
                        if not birth_date and pd.notna(birth_year):
                            try:
                                year_int = int(float(birth_year))
                                birth_date = datetime(year_int, 1, 1).date()
                            except:
                                pass
                        
                        if not birth_date:
                            # Final fallback to avoid NOT NULL error
                            birth_date = datetime(2000, 1, 1).date()
                        
                        yosh = Yosh.objects.create(
                            fullname=fullname,
                            passport_number=passport if passport and passport != 'nan' else '',
                            jshshir=jshshir,
                            phone_number=phone if phone and phone != 'nan' else '',
                            mahalla=mahalla,
                            birth_date=birth_date,
                            address=f"{mahalla.name} mahallasi"
                        )
                        created_yosh_count += 1
                    except Exception as e:
                        errors.append(f"Qator {index + 3}: Yosh yaratishda xato - {fullname}: {str(e)}")
                        continue
                else:
                    # Optional: update mahalla of existing Yosh if different?
                    # For now keep as is per requirement "checks if exists"
                    pass
                
                # 3. Map category
                category = 'QOLGAN'  # Default
                if category_text and category_text != 'nan':
                    category_lower = category_text.lower()
                    if 'migrat' in category_lower:
                        category = 'MIGRATSIYA'
                    elif 'maktab' in category_lower:
                        category = 'MAKTAB'
                    elif 'kasb' in category_lower or 'kush' in category_lower or 'texnikum' in category_lower:
                        category = 'KASBIY'
                    elif 'oliy' in category_lower or 'otm' in category_lower or 'universitet' in category_lower or 'institut' in category_lower:
                        category = 'OLIY'
                    elif 'qolgan' in category_lower:
                        category = 'QOLGAN'
                    elif 'yoshlar' in category_lower and 'band' not in category_lower: # Catch-all for other unemployed terms
                        category = 'QOLGAN'
                
                # 4. Find or create responsible leader
                leader = None
                if leader_fio and leader_fio != 'nan':
                    # Map level
                    level = 'TUMAN'  # Default
                    if leader_level and leader_level != 'nan':
                        level_lower = leader_level.lower()
                        if 'respublika' in level_lower:
                            level = 'RESPUBLIKA'
                        elif 'viloyat' in level_lower:
                            level = 'VILOYAT'
                        elif 'otm' in level_lower or 'alohida' in level_lower:
                            level = 'OTM'
                    
                    leader, _ = ResponsibleLeader.objects.get_or_create(
                        full_name=leader_fio,
                        defaults={
                            'position': leader_position if leader_position and leader_position != 'nan' else '',
                            'level': level
                        }
                    )
                
                # 5. Create UnemployedYouth record
                obj, created = UnemployedYouth.objects.get_or_create(
                    yosh=yosh,
                    defaults={
                        'category': category,
                        'leader': leader
                    }
                )
                
                if created:
                    imported_count += 1
                else:
                    # Update if already exists
                    obj.category = category
                    if leader:
                        obj.leader = leader
                    obj.save()
                    
        except Exception as e:
            errors.append(f"Qator {index + 3}: Kutilmagan xato - {str(e)}")
    
    return imported_count, created_yosh_count, errors


