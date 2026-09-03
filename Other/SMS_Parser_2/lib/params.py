import os.path
WORKING_DIRECTORY = r'./'
SMS_TEXT_DIRECTORY = 'SMS_TEXTS'

LOG_FILE_NAME = os.path.join(WORKING_DIRECTORY, 'sms_parse_runlog.txt')

PROVIDERS = {
    'Stream': r'./Stream Telecom — декабрь.csv',
    'SMS_RU': r'./SMS.ru – декабрь.csv'
}