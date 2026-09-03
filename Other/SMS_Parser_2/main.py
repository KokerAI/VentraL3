# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.

import lib.logic
import lib.params
import lib.source
import logging

logging.basicConfig(encoding='UTF-8', filename=lib.params.LOG_FILE_NAME)


logic = lib.logic.Logic()
source = lib.source.Source()

for provider in lib.params.PROVIDERS:
    source.process_source(provider, logic)

logic.write_report()
