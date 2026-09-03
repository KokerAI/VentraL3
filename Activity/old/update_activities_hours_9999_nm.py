import requests

# Изменить подтвержденное количество минут из статусов:
# FUNDS_AVAILABLE
# TIME_APPROVED
# WORKER_PAID_FULLY (только увеличение количетсва минут)

with open('D:/WORK/python/auth.txt') as f:
    auth = f.readline().strip()
host = 'sdr-api.dap.ventra.ru/payment-transactions'


def update_activities_hours(activities_id, minutes):
    headers = {'Authorization': auth.strip(), 'content-type': 'application/json'}
    params = {
        'activityId': activities_id,
        'minutes': minutes,
    }
    endpoint_url = f'https://{host}/ops/update-confirmed-hours'
    r = requests.patch(endpoint_url, headers=headers, params=params)
    return r, r.text


activities_id = []
with open('D:/WORK/python/list_activities.txt', 'r') as file:
    for line in file:
        activities_id.append(line.strip())

minutes = []
with open('D:/WORK/python/list_minutes.txt', 'r') as file:
    for mins in file:
        minutes.append(mins.strip())

if len(activities_id) != len(minutes):
    print("Количество activityId и минут не совпадает!")
    exit(1)

total = len(activities_id)
cnt = 0

for i in range(total):
    status, response = update_activities_hours(activities_id[i], minutes[i])
    print(f"{activities_id[i]}, {minutes[i]}, Status: {status}, Response: {response}")
    cnt += 1
    print(f"Сделано {cnt} из {total}.")
