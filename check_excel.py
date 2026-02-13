import pandas as pd
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    df = pd.read_excel('ishsiz yoshlar 2026.xlsx')
    logger.info("Columns in Excel:")
    logger.info(df.columns.tolist())
    logger.info("\nFirst 5 rows:")
    logger.info(df.head())
except FileNotFoundError as e:
    logger.error(f"File not found: {e}")
except Exception as e:
    logger.error(f"Error reading Excel file: {e}", exc_info=True)
