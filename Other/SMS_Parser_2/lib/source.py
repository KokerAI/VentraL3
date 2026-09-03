import lib.logic as logic
import lib.params as params
import lib.dto as dto

import csv

class Source:
    def __init__(self):
        self.open_files = []

    def __del__(self):
        for file in self.open_files:
            file.close()

    def process_source(self, provider: str, logic: logic.Logic):
        csv_reader = self.get_reader(provider)
        begin = True
        for row in csv_reader:
            if begin:
                begin = False
                continue
            sms_data = self.read_line(provider, row)
            logic.classify_sms(sms_data)


    def get_reader(self, provider: str):
        input_file_name = params.PROVIDERS[provider]

        if provider == 'Stream':
            input_file = open(input_file_name, 'r', encoding='UTF-8', newline='')
            self.open_files.append(input_file)

            header = '"Название рассылки";"Направление";"Оператор";"Отправитель";"Номер";"Время получения статуса";"Время отправки";"Текст SMS";"Частей";"Статус";"Цена";"Тип шаблона"'
            return csv.DictReader(input_file, delimiter=';', fieldnames=header.split(';'), dialect='excel', quoting=csv.QUOTE_ALL)

        elif provider == 'SMS_RU':
            input_file = open(input_file_name, 'r', encoding='windows-1251', newline='')
            self.open_files.append(input_file)

            header = '"Дата отправки";Номер;Текст;Отправитель;СМС;Цена;Статус;"Дата статуса"'
            return csv.DictReader(input_file, delimiter=';', fieldnames=header.split(';'), dialect='excel', quotechar='"')
        else:
            raise Exception(f'Не описан обработчик source для провайдера {provider}')

    def read_line(self, provider, row) -> dto.SmsData:
        if provider == "SMS_RU":
            return dto.SmsData(
                provider=provider,
                text=row['Текст'],
                sms_count=int(row['СМС']),
                cost= float(str(row['Цена']).replace(',', '.'))
            )
        elif provider == 'Stream':
            return dto.SmsData(
                provider=provider,
                text=row['"Текст SMS"'],
                sms_count=int(row['"Частей"']),
                cost=float(str(row['"Цена"']).replace(',', '.'))
            )
        else:
            raise Exception(f'Не описан обработчик source_line для провайдера {provider}')