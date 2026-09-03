import re
import logging
import os

import lib.dto
from lib.pattern_list import PatternList
import lib.params


class Logic:

    def __init__(self):
        self.result_list = {}
        self.patterns = PatternList()
        self.result_holder = lib.dto.ResultHolder()
        self.sms_writer = lib.dto.SmsTextWriter()

    def classify_sms(self, sms_row: lib.dto.SmsData) -> bool:
        match_found = False
        for pattern_type in self.patterns.pattern_dic:
            pattern = self.patterns.pattern_dic[pattern_type]
            match = re.search(pattern=pattern.combined_pattern, string=sms_row.text)
            if match:
                match_found = True
                log_msg = f'Классификация: txt = [{sms_row.text}], type = {pattern.type}'
                logging.debug(log_msg)

                self.result_holder.append_result(pattern, sms_row)
                self.sms_writer.write_sms_text(pattern, sms_row)

                break

        if not match_found:
            other_pattern = lib.dto.Pattern(type='Other', pattern_array=['.'], example=['any'])
            self.result_holder.append_result(other_pattern, sms_row)
            msg = f'Не найдено сопоставление для текста: {sms_row.text}'
            logging.error(msg)
            return False
        else:
            return True

    def write_report(self):
        self.result_holder.write_report()
