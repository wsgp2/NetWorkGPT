#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
NetWorkGPT - u0438u043du0442u0435u043bu043bu0435u043au0442u0443u0430u043bu044cu043du0430u044f u0441u0438u0441u0442u0435u043cu0430 u0443u043fu0440u0430u0432u043bu0435u043du0438u044f u043au043eu043du0442u0430u043au0442u0430u043cu0438
u041eu0431u044au0435u0434u0438u043du044fu0435u0442 Telegram u0438 Google Contacts u0441 AI-u0430u043du0430u043bu0438u0442u0438u043au043eu0439

u0410u0432u0442u043eu0440: u0421u0435u0440u0433u0435u0439 u0414u044bu0448u043au0430u043du0442 (c) 2025
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# u0414u043eu0431u0430u0432u043bu044fu0435u043c u043au043eu0440u043du0435u0432u0443u044e u0434u0438u0440u0435u043au0442u043eu0440u0438u044e u0432 sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from loguru import logger

from src.bot.telegram_bot import TelegramBot
from src.database.database import DatabaseManager
from src.sync.sync_manager import SyncManager
from src.utils.config import load_config


async def main():
    """u041eu0441u043du043eu0432u043du0430u044f u0444u0443u043du043au0446u0438u044f u0437u0430u043fu0443u0441u043au0430 u043fu0440u0438u043bu043eu0436u0435u043du0438u044f"""
    parser = argparse.ArgumentParser(description="NetWorkGPT - u0438u043du0442u0435u043bu043bu0435u043au0442u0443u0430u043bu044cu043du0430u044f u0441u0438u0441u0442u0435u043cu0430 u0443u043fu0440u0430u0432u043bu0435u043du0438u044f u043au043eu043du0442u0430u043au0442u0430u043cu0438")
    parser.add_argument("--config", type=str, default="configs/config.yaml", help="u041fu0443u0442u044c u043a u0444u0430u0439u043bu0443 u043au043eu043du0444u0438u0433u0443u0440u0430u0446u0438u0438")
    parser.add_argument("--debug", action="store_true", help="u0412u043au043bu044eu0447u0438u0442u044c u0440u0435u0436u0438u043c u043eu0442u043bu0430u0434u043au0438")
    args = parser.parse_args()
    
    # u0417u0430u0433u0440u0443u0437u043au0430 u043au043eu043du0444u0438u0433u0443u0440u0430u0446u0438u0438
    config_path = Path(root_dir) / args.config
    config = load_config(config_path)
    
    # u041du0430u0441u0442u0440u043eu0439u043au0430 u043bu043eu0433u0438u0440u043eu0432u0430u043du0438u044f
    log_level = "DEBUG" if args.debug else config["logging"]["level"]
    log_file = Path(root_dir) / config["logging"]["file"]
    log_file.parent.mkdir(exist_ok=True, parents=True)
    
    # u041au043eu043du0444u0438u0433u0443u0440u0430u0446u0438u044f u043bu043eu0433u0433u0435u0440u0430
    logger.remove()  # u0423u0434u0430u043bu044fu0435u043c u0441u0442u0430u043du0434u0430u0440u0442u043du044bu0439 u043eu0431u0440u0430u0431u043eu0442u0447u0438u043a
    logger.add(sys.stderr, level=log_level)  # u0412u044bu0432u043eu0434 u0432 u043au043eu043du0441u043eu043bu044c
    logger.add(
        str(log_file),
        rotation=f"{config['logging']['max_size_mb']} MB",
        retention=config["logging"]["backup_count"],
        level=log_level,
        encoding="utf-8"
    )
    
    logger.info(f"NetWorkGPT u0437u0430u043fu0443u0441u043au0430u0435u0442u0441u044f... u0420u0435u0436u0438u043c u043eu0442u043bu0430u0434u043au0438: {args.debug}")
    
    try:
        # u0418u043du0438u0446u0438u0430u043bu0438u0437u0430u0446u0438u044f u0431u0430u0437u044b u0434u0430u043du043du044bu0445
        db_config = config["database"]
        db_url = f"postgresql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['name']}"
        db_manager = DatabaseManager(db_url)
        await db_manager.initialize()
        logger.info("u0411u0430u0437u0430 u0434u0430u043du043du044bu0445 u0443u0441u043fu0435u0448u043du043e u0438u043du0438u0446u0438u0430u043bu0438u0437u0438u0440u043eu0432u0430u043du0430")
        
        # u0418u043du0438u0446u0438u0430u043bu0438u0437u0430u0446u0438u044f u043cu0435u043du0435u0434u0436u0435u0440u0430 u0441u0438u043du0445u0440u043eu043du0438u0437u0430u0446u0438u0438
        sync_manager = SyncManager(config, db_manager)
        
        # u0417u0430u043fu0443u0441u043a Telegram u0431u043eu0442u0430
        bot = TelegramBot(config, db_manager, sync_manager)
        await bot.start()
        
    except Exception as e:
        logger.exception(f"u041eu0448u0438u0431u043au0430 u043fu0440u0438 u0437u0430u043fu0443u0441u043au0435 u043fu0440u0438u043bu043eu0436u0435u043du0438u044f: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        # u0421u043eu0437u0434u0430u043du0438u0435 u0438 u0437u0430u043fu0443u0441u043a u0446u0438u043au043bu0430 u0441u043eu0431u044bu0442u0438u0439
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("u041fu0440u0438u043bu043eu0436u0435u043du0438u0435 u043eu0441u0442u0430u043du043eu0432u043bu0435u043du043e u043fu043eu043bu044cu0437u043eu0432u0430u0442u0435u043bu0435u043c")
        sys.exit(0)
