import os
import django
import pandas as pd
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.models import Yosh, Mahalla

def import_yoshlar(file_path):
    logger.info(f"Reading {file_path}...")
    try:
        # Read all data
        df = pd.read_excel(file_path)
        logger.info(f"Total rows found: {len(df)}")

        # 1. Clean data and handle Mahallas
        # Fill nan with empty strings or sensible defaults
        df = df.fillna('')
        
        unique_mahallas = df['Mahalla'].unique()
        mahalla_map = {}
        
        logger.info(f"Processing {len(unique_mahallas)} unique mahallas...")
        for m_name in unique_mahallas:
            if not m_name: 
                continue
            obj, created = Mahalla.objects.get_or_create(name=m_name)
            mahalla_map[m_name] = obj

        # 2. Prepare Yosh objects
        yosh_objects = []
        
        logger.info("Preparing data for import...")
        for index, row in df.iterrows():
            try:
                # Fullname
                fullname = f"{row['Familyasi']} {row['Ismi']} {row['Otasining ismi']}".strip()
                
                # Date conversion
                bdate_str = str(row["Tug'ilgan sanasi"])
                try:
                    # Format 10.09.1995
                    birth_date = datetime.strptime(bdate_str, '%d.%m.%Y').date()
                except ValueError:
                    logger.warning(f"Invalid date format at row {index}: {bdate_str}")
                    birth_date = datetime(2000, 1, 1).date()
                
                # Passport & JSHSHIR as string
                pass_num = str(row['Passport']).strip()
                jshshir = str(row['JSHSHIR']).split('.')[0] # Remove .0 if float
                
                # Mahalla object
                mahalla_obj = mahalla_map.get(row['Mahalla'])
                if not mahalla_obj:
                    logger.warning(f"Mahalla not found for row {index}: {row['Mahalla']}")
                    continue

                yosh_obj = Yosh(
                    fullname=fullname,
                    birth_date=birth_date,
                    passport_number=pass_num,
                    jshshir=jshshir,
                    address=str(row['Yashash manzili']),
                    phone_number=str(row['Telefon raqami']),
                    mahalla=mahalla_obj,
                    photo='yoshlar_photos/default.jpg' # Placeholder photo path
                )
                yosh_objects.append(yosh_obj)
                
                if len(yosh_objects) >= 2000:
                    Yosh.objects.bulk_create(yosh_objects)
                    logger.info(f"Imported {index + 1} records...")
                    yosh_objects = []
                    
            except Exception as e:
                logger.error(f"Error at row {index}: {str(e)}", exc_info=True)
    
        # Final batch
        if yosh_objects:
            Yosh.objects.bulk_create(yosh_objects)
            logger.info(f"Completed! Final batch imported.")
    
    except Exception as e:
        logger.error(f"Fatal error during import: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    file_path = r"d:\Dev projects\Yoshlar\yoshlar.xlsx"
    try:
        import_yoshlar(file_path)
    except Exception as e:
        logger.critical(f"Import failed: {str(e)}", exc_info=True)
