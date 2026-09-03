import csv
import os.path
from dataclasses import dataclass
import lib.params


@dataclass
class Pattern:
    type: str
    pattern_array: list[str]
    example: list[str]
    combined_pattern: str = None
    subtype: str = None

    def to_json(self):
        return self.__dict__


@dataclass
class SmsData:
    provider: str
    text: str
    sms_count: int
    cost: float

    def inline_text(self) -> str:
        return str.replace(self.text, '\n', ' ')


@dataclass
class SmsProviderInfo:
    provider_type: str
    row_count: int
    sms_count: int
    total_cost: float

    def __init__(self, sms: SmsData):
        self.provider_type = sms.provider
        self.row_count = 1
        self.sms_count = sms.sms_count
        self.total_cost = sms.cost

    def append_data(self, sms: SmsData):
        self.row_count += 1
        self.sms_count += sms.sms_count
        self.total_cost += sms.cost


class ClassifyResult:
    def __init__(self, pattern: Pattern, sms_row: SmsData):
        self.type = pattern.type
        provider_info = SmsProviderInfo(sms_row)
        self.per_provider_data_dic = {
            sms_row.provider: provider_info
        }

    def append_result(self, pattern: Pattern, sms_row: SmsData):
        if sms_row.provider in self.per_provider_data_dic:
            provider: SmsProviderInfo = self.per_provider_data_dic[sms_row.provider]
            provider.append_data(sms_row)
        else:
            provider_info = SmsProviderInfo(sms_row)
            self.per_provider_data_dic[sms_row.provider] = provider_info


class ResultHolder:

    def __init__(self):
        self.per_pattern_result_dic = {}

    def append_result(self, pattern: Pattern, sms_row: SmsData):
        if pattern.type in self.per_pattern_result_dic:
            res: ClassifyResult = self.per_pattern_result_dic[pattern.type]
            res.append_result(pattern, sms_row)
        else:
            res = ClassifyResult(pattern, sms_row)
            self.per_pattern_result_dic[pattern.type] = res

    def write_report(self):
        report_file_name = os.path.join(lib.params.WORKING_DIRECTORY, 'sms_report.csv')
        providers = []
        report_lines = []

        # Первый проход - определяем всех провайдеров
        for pattern_type in self.per_pattern_result_dic:
            result: ClassifyResult = self.per_pattern_result_dic[pattern_type]
            for provider in result.per_provider_data_dic:
                if provider not in providers:
                    providers.append(provider)

        header_line = 'pattern;total_row_count;total_sms_count'
        for provider in providers:
            header_line += f';{provider}_row_count;{provider}_sms_count;{provider}_total_cost'

        # Второй проход - формирование отчета
        for pattern_type in self.per_pattern_result_dic:
            result: ClassifyResult = self.per_pattern_result_dic[pattern_type]

            total_row_count = 0
            total_sms_count = 0

            report_line = {'pattern': pattern_type}
            for provider in result.per_provider_data_dic:
                provider_data: SmsProviderInfo = result.per_provider_data_dic[provider]
                report_line[f'{provider}_row_count'] = provider_data.row_count
                report_line[f'{provider}_sms_count'] = provider_data.sms_count
                report_line[f'{provider}_total_cost'] = f'{provider_data.total_cost:9.2f}'
                total_row_count += provider_data.row_count
                total_sms_count += provider_data.sms_count

            report_line['total_row_count'] = total_row_count
            report_line['total_sms_count'] = total_sms_count

            report_lines.append(report_line)

        try:
            report_file = open(report_file_name, 'w', encoding='UTF-8', newline='')
            csv_writer = csv.DictWriter(report_file, delimiter=';', fieldnames=header_line.split(';'), dialect='excel')

            csv_writer.writeheader()

            for line in report_lines:
                csv_writer.writerow(line)

        finally:
            if report_file is not None:
                report_file.close()


class SmsTextWriter:
    def __init__(self):
        self.open_files = {}

    def __del__(self):
        for open_file in self.open_files:
            self.open_files[open_file].close()

    def write_sms_text(self, pattern: Pattern, sms: SmsData):
        text_to_write = sms.inline_text() + '\n'
        if pattern.type in self.open_files:
            file = self.open_files[pattern.type]
            file.write(text_to_write)
        else:
            file_name = self.make_file_name(pattern)
            file = open(file_name, 'w', encoding='UTF-8', newline='')
            self.open_files[pattern.type] = file
            file.write(text_to_write)

    def make_file_name(self, pattern: Pattern):
        sms_text_file_name = f'''sms_type_{pattern.type.replace(' ', '_')}.txt'''

        return os.path.join(lib.params.WORKING_DIRECTORY, lib.params.SMS_TEXT_DIRECTORY,
                            sms_text_file_name)
