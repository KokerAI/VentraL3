import pandas as pd
import logging
from pathlib import Path
import re
import sqlalchemy as sa


file_dir = Path('./Alfa/2025.02/')
logging.basicConfig(level=logging.DEBUG, filename='billing.log', filemode='a',
                    format='%(asctime)s %(levelname)s %(message)s')

db_string = ("postgresql://z.khairudinov:pM93vRJjDGXU1-rKB6MU@prod-dap-db1.msk.ventrago.dev/production")
db = sa.create_engine(db_string, pool_use_lifo=True, pool_pre_ping=True)
def sql_select_transaction(pt_uuid):
        #print(pt_uuid)
    sql_text = sa.text(f"select pt.uuid, "
                       f"        pt.created_at + interval '3 hours' as pt_created_at, "
                       f"        concat(coalesce(initcap(eu.last_name_passport), "
                       f"               coalesce(u.last_name, null)), ' ',  "
                       f"               coalesce(initcap(eu.first_name_passport), "
                       f"               coalesce(u.first_name , null)), ' ', "
                       f"               coalesce(initcap(eu.middle_name_passport), "
                       f"               coalesce(u.middle_name, null))) as exec_name, "
                       f"         eu.code_inn, abs(pt.amount) as amount, "
                       f"         pt.description, "
                       f"         pt.commission, cc.\"number\" as card_number, "
                       f"         pt.provider, "
                       f"         p.\"name\" as project_name, "
                       f"         b.title as breand_name, "
                       f"         b.deal_code, "
                       f"         pt.fns_generated_receipt_url, "
                       f"         pt.fns_generated_receipt_id, "
                       f"         pt.status, "
                       f"         pt.id, "
                       f"         pt.need_fiscalization, "
                       f"         pt.\"type\" "
                       f"    from payment_transaction pt "
                       f"    left join credit_cards cc on cc.user_id = pt.entity_id "
                       f"              and cc.\"token\" = pt.executor_card_id::varchar "
                       f"    join executor_users eu on eu.id = pt.entity_id "
                       f"    join users u on u.id = eu.id "
                       f"    left join executor_work_activity ewa on ewa.id = pt.executor_work_activity_id "
                       f"    left join vacancies v on v.id = ewa.vacancy_id "
                       f"    left join projects p on p.id = v.project_id "
                       f"    left join brands b on b.id = p.brand_id "
                       f"    where pt.uuid = '{pt_uuid}' "
                       f"    order by pt.created_at;")
    #print(sql_text)
    with db.connect() as conn:
        q = conn.execute(sql_text)
        raw = q.fetchall()
        conn.commit()
        conn.close()
        #print(raw)
        transaction_info = {'uuid': raw[0][0],
                            'pt_created_at': raw[0][1],
                            'exec_name': raw[0][2],
                            'code_inn': raw[0][3],
                            'amount': raw[0][4],
                            'description': raw[0][5],
                            'commission': raw[0][6],
                            'card_number': raw[0][7],
                            'provider':  raw[0][8],
                            'project_name': raw[0][9],
                            'breand_name': raw[0][10],
                            'deal_code': raw[0][11],
                            'fns_generated_receipt_url': raw[0][12],
                            'fns_generated_receipt_id': raw[0][13],
                            'status': raw[0][14],
                            'id':  raw[0][15],
                            'need_fiscalization': raw[0][16],
                            'type': raw[0][17]
                            }
    return transaction_info


df_csv = pd.concat([pd.read_csv(f, encoding='windows-1251', delimiter=';') for f in file_dir.glob('*.csv')], ignore_index=True)
df_csv = df_csv.sort_values(by=['Дата Время'])
df_csv['UUID'] = 'NAN'
df_csv['Сумма Вентра'] = 'NAN'
df_csv['Комиссия Вентра'] = 'NAN'
df_csv['ИНН'] = 'NAN'
df_csv['ФИО'] = 'NAN'
df_csv['Ссылка на чек'] = 'NAN'
df_csv['Основание'] = 'NAN'
df_csv['Проект'] = 'NAN'
df_csv['Бранд'] = 'NAN'
df_csv['Код Сделки'] = 'NAN'
for index, row in df_csv.iterrows():
    comment = df_csv.at[index, 'Комментарий']
    t_uuid = re.search("\[(.+?)\]", comment).group(1)
    #print(t_uuid)
    logging.info(f'Запрпаштваем инфо по транзакции {t_uuid}')
    t_detail = sql_select_transaction(t_uuid)
    logging.info(f'Получили инфо: {t_detail}')
    df_csv.at[index, 'UUID'] = t_uuid
    df_csv.at[index, 'Сумма Вентра'] = t_detail['amount']
    df_csv.at[index, 'Комиссия Вентра'] = t_detail['commission']
    df_csv.at[index, 'ИНН'] = t_detail['code_inn']
    df_csv.at[index, 'ФИО'] = t_detail['exec_name']
    df_csv.at[index, 'Ссылка на чек'] = t_detail['fns_generated_receipt_url']
    df_csv.at[index, 'Основание'] = t_detail['description']
    df_csv.at[index, 'Проект'] = t_detail['project_name']
    df_csv.at[index, 'Бранд'] = t_detail['breand_name']
    df_csv.at[index, 'Код Сделки'] = t_detail['deal_code']
    logging.info(f'Добавили в датафрейм')
# print(sql_select_transaction('2205be5f-b9dd-4c5a-b1cd-8e2050a7d10e'))

logging.info('Начали сохранять...')
df_csv.to_excel(file_dir.joinpath('out.xlsx'), index=False)
logging.info('Закончили...')