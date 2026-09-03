#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Улучшенный скрипт для массовой миграции медкнижек ГПХ в формат медкнижек СМЗ
Автор: z.khairudinov
"""

import psycopg2
import json
import sys
import argparse
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# Конфигурация подключения к базе данных
DB_CONFIG = {
    'host': 'prod-dap-db1.msk.ventrago.dev',
    'database': 'production',
    'user': 'z.khairudinov',
    'password': '9bO8-Vvbzcz-DYVjvG66',
    'port': 5432
}

# Схема БД (если используется)
DB_SCHEMA = 'public'

# ID шаблонов документов
SMZ_TEMPLATE_ID = 44151  # Медкнижка СМЗ
GPH_TEMPLATE_ID = 267587910  # Медкнижка ГПХ

class MedicalBookMigrator:
    def __init__(self, db_config: Dict, executor_ids: Optional[List[int]] = None):
        self.db_config = db_config
        self.connection = None
        self.executor_ids = executor_ids
        self.migration_stats = {
            'total_documents': 0,
            'successful_migrations': 0,
            'failed_migrations': 0,
            'skipped_documents': 0,
            'start_time': None,
            'end_time': None
        }
        
    def connect(self):
        """Подключение к базе данных"""
        try:
            self.connection = psycopg2.connect(
                **self.db_config,
                client_encoding='utf8'
            )
            print("Подключение к базе данных установлено")
        except Exception as e:
            print(f"Ошибка подключения к БД: {e}")
            raise
    
    def disconnect(self):
        """Отключение от базы данных"""
        if self.connection:
            self.connection.close()
            print("Соединение с БД закрыто")
    
    def analyze_database_structure(self):
        """Анализ структуры базы данных"""
        print(f"\nАнализ структуры базы данных...")
        print(f"База данных: {self.db_config['database']}")
        print(f"Схема: {DB_SCHEMA}")
        
        cursor = self.connection.cursor()
        
        # Получаем список таблиц
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = %s 
            AND table_name IN ('executors_document', 'field_documents', 'template_executors_document', 'template_fields_document')
            ORDER BY table_name;
        """, (DB_SCHEMA,))
        
        tables = [row[0] for row in cursor.fetchall()]
        print(f"\nНайдено таблиц: {len(tables)}")
        for table in tables:
            print(f"   - {table}")
        
        # Анализируем структуру каждой таблицы
        for table in tables:
            print(f"\nТаблица: {table}")
            print("-" * 50)
            try:
                cursor.execute("""
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_schema = %s AND table_name = %s
                    ORDER BY ordinal_position;
                """, (DB_SCHEMA, table))
                
                columns = cursor.fetchall()
                for col in columns:
                    nullable = 'NULL' if col[2] == 'YES' else 'NOT NULL'
                    default = f" DEFAULT {col[3]}" if col[3] else ""
                    print(f"  {col[0]:<30} {col[1]:<20} {nullable}{default}")
                    
            except Exception as e:
                print(f"Ошибка при анализе таблицы {table}: {e}")
    
    def get_document_templates(self):
        """Получение информации о шаблонах документов"""
        print(f"\nАнализ шаблонов документов...")
        
        cursor = self.connection.cursor()
        
        # Получаем информацию о шаблонах СМЗ и ГПХ
        cursor.execute("""
            SELECT id, name, instruction, rate, editable, type
            FROM template_executors_document 
            WHERE id IN (%s, %s)
            ORDER BY id;
        """, (SMZ_TEMPLATE_ID, GPH_TEMPLATE_ID))
        
        templates = cursor.fetchall()
        
        for template in templates:
            template_id, name, instruction, rate, editable, template_type = template
            doc_type = "СМЗ" if template_id == SMZ_TEMPLATE_ID else "ГПХ"
            print(f"\n{doc_type} Медкнижка (ID: {template_id})")
            print(f"   Название: {name}")
            print(f"   Инструкция: {instruction[:100]}..." if instruction else "   Инструкция: None")
            print(f"   Ставка: {rate}")
            print(f"   Редактируемый: {editable}")
            print(f"   Тип: {template_type}")
        
        return templates
    
    def get_field_mappings(self):
        """Получение маппинга полей для шаблонов"""
        print(f"\nАнализ полей документов...")
        
        cursor = self.connection.cursor()
        
        # Получаем поля для СМЗ медкнижки
        cursor.execute("""
            SELECT fd.id, fd.name, fd.type, fd.required, fd.default_name
            FROM template_fields_document fd
            WHERE fd.template_fields_document_id = %s
            ORDER BY fd.id;
        """, (SMZ_TEMPLATE_ID,))
        
        smz_fields = cursor.fetchall()
        print(f"\nПоля для СМЗ медкнижки (ID: {SMZ_TEMPLATE_ID}):")
        for field in smz_fields:
            field_id, name, field_type, required, default_name = field
            required_str = " *" if required else ""
            print(f"   {field_id}. {name} ({field_type}){required_str} - {default_name}")
        
        # Получаем поля для ГПХ медкнижки
        cursor.execute("""
            SELECT fd.id, fd.name, fd.type, fd.required, fd.default_name
            FROM template_fields_document fd
            WHERE fd.template_fields_document_id = %s
            ORDER BY fd.id;
        """, (GPH_TEMPLATE_ID,))
        
        gph_fields = cursor.fetchall()
        print(f"\nПоля для ГПХ медкнижки (ID: {GPH_TEMPLATE_ID}):")
        for field in gph_fields:
            field_id, name, field_type, required, default_name = field
            required_str = " *" if required else ""
            print(f"   {field_id}. {name} ({field_type}){required_str} - {default_name}")
        
        return smz_fields, gph_fields
    
    def get_gph_documents(self):
        """Получение ГПХ документов для миграции"""
        print(f"\nПоиск ГПХ документов для миграции...")
        
        cursor = self.connection.cursor()
        
        # Базовый запрос для получения ГПХ документов
        base_query = """
            SELECT 
                ed.id,
                ed.executor_id,
                ed.template_document_id,
                ed.executors_document_status,
                ed.name,
                ed.creation_date,
                ed.rejection_reason,
                ed.archive,
                ed.instruction,
                ed.banner_shown,
                ed.date_moved_to_archive,
                ed.req_number,
                ed.auto_confirmed
            FROM executors_document ed
            WHERE ed.template_document_id = %s
            AND ed.executors_document_status = 'APPROVE'
        """
        
        params = [GPH_TEMPLATE_ID]
        
        # Добавляем фильтр по исполнителям, если указан
        if self.executor_ids:
            placeholders = ','.join(['%s'] * len(self.executor_ids))
            base_query += f" AND ed.executor_id IN ({placeholders})"
            params.extend(self.executor_ids)
            print(f"   Фильтрация по исполнителям: {len(self.executor_ids)} ID")
            print(f"   Список ID исполнителей: {self.executor_ids}")
        
        base_query += " ORDER BY ed.creation_date;"
        
        cursor.execute(base_query, params)
        gph_documents = cursor.fetchall()
        
        print(f"   Найдено ГПХ медкнижек со статусом APPROVE: {len(gph_documents)}")
        
        # Показываем статистику по статусам для информации
        if self.executor_ids:
            cursor.execute("""
                SELECT executors_document_status, COUNT(*)
                FROM executors_document 
                WHERE template_document_id = %s 
                AND executor_id IN ({})
                GROUP BY executors_document_status
                ORDER BY executors_document_status
            """.format(','.join(['%s'] * len(self.executor_ids))), 
            [GPH_TEMPLATE_ID] + self.executor_ids)
            
            status_stats = cursor.fetchall()
            print(f"   Статистика по статусам:")
            for status, count in status_stats:
                print(f"      {status}: {count} документов")
        
        return gph_documents
    
    def analyze_document_data(self, documents: List[Tuple]):
        """Анализ структуры данных в документах"""
        print(f"\nАнализ структуры данных документов...")
        
        if not documents:
            print("   Нет документов для анализа")
            return
        
        # Анализируем первые несколько документов
        sample_size = min(5, len(documents))
        field_analysis = {}
        
        for i, doc in enumerate(documents[:sample_size]):
            (doc_id, executor_id, template_id, status, name, creation_date, 
             rejection_reason, archive, instruction, banner_shown, date_moved_to_archive, 
             req_number, auto_confirmed) = doc
            
            print(f"\n   Документ {i+1} (ID: {doc_id}):")
            print(f"      Исполнитель: {executor_id}")
            print(f"      Статус: {status}")
            print(f"      Название: {name}")
            print(f"      Дата создания: {creation_date}")
            print(f"      Архив: {archive}")
            
            # Получаем данные полей из field_documents
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT fd.value, tfd.name, tfd.type
                FROM field_documents fd
                JOIN template_fields_document tfd ON fd.template_fields_id = tfd.id
                WHERE fd.fields_document_id = %s
            """, (doc_id,))
            
            field_data = {}
            for value, field_name, field_type in cursor.fetchall():
                field_data[field_name] = value
            
            print(f"      Поля документа:")
            if field_data:
                for field_name, field_value in field_data.items():
                    print(f"         {field_name}: {field_value}")
            else:
                print(f"         (данные не найдены)")
            
            # Анализируем статистику полей
            for field_name in field_data.keys():
                if field_name not in field_analysis:
                    field_analysis[field_name] = 0
                field_analysis[field_name] += 1
        
        print(f"\n   Статистика полей (из {sample_size} документов):")
        for field_name, count in field_analysis.items():
            print(f"      {field_name}: {count}/{sample_size} документов")
    
    def get_smz_field_mappings(self):
        """Получение маппинга полей СМЗ"""
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT fd.id, fd.name
            FROM template_fields_document fd
            WHERE fd.template_fields_document_id = %s
        """, (SMZ_TEMPLATE_ID,))
        
        field_mappings = {}
        for field_id, field_name in cursor.fetchall():
            field_mappings[field_name] = field_id
        
        return field_mappings
    
    def create_smz_template_executor_document(self):
        """Создание template для СМЗ документов"""
        print(f"\nСоздание template для СМЗ документов...")
        
        # Проверяем, существует ли уже template для СМЗ
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT id FROM template_executors_document 
            WHERE id = %s
        """, (SMZ_TEMPLATE_ID,))
        
        if cursor.fetchone():
            print(f"   Template СМЗ уже существует (ID: {SMZ_TEMPLATE_ID})")
            return SMZ_TEMPLATE_ID
        
        print(f"   Template СМЗ не найден, создаем новый...")
        return SMZ_TEMPLATE_ID
    
    def migrate_document(self, gph_doc: Tuple, smz_template_executor_id: int) -> bool:
        """Миграция одного документа из ГПХ в СМЗ формат"""
        (doc_id, executor_id, template_id, status, name, creation_date, 
         rejection_reason, archive, instruction, banner_shown, date_moved_to_archive, 
         req_number, auto_confirmed) = gph_doc
        
        try:
            # Получаем данные ГПХ документа из field_documents
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT fd.value, tfd.name, tfd.type
                FROM field_documents fd
                JOIN template_fields_document tfd ON fd.template_fields_id = tfd.id
                WHERE fd.fields_document_id = %s
            """, (doc_id,))
            
            gph_data = {}
            for value, field_name, field_type in cursor.fetchall():
                gph_data[field_name] = value
            
            # Маппинг полей ГПХ -> СМЗ
            smz_data = {}
            
            # Прямое копирование полей
            if 'Номер' in gph_data:
                smz_data['Номер'] = gph_data['Номер']
            
            if 'Дата выдачи' in gph_data:
                smz_data['Дата выдачи'] = gph_data['Дата выдачи']
            
            if 'Дата окончания действия' in gph_data:
                smz_data['Дата окончания действия'] = gph_data['Дата окончания действия']
            
            # Поле "Кем выдан" отсутствует в ГПХ - устанавливаем значение по умолчанию
            smz_data['Кем выдан'] = 'Не указано (мигрировано из ГПХ)'
            
            current_time = datetime.now()
            
            # Используем правильное название для СМЗ медкнижки
            smz_template_name = "Медицинская книжка/справка"
            
            # 1. Создаем новый документ СМЗ в executors_document
            cursor.execute("""
                INSERT INTO executors_document (
                    executor_id,
                    template_document_id,
                    executors_document_status,
                    name,
                    creation_date,
                    rejection_reason,
                    archive,
                    instruction,
                    banner_shown,
                    date_moved_to_archive,
                    req_number,
                    auto_confirmed
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
            """, (
                executor_id,
                smz_template_executor_id,
                status,  # Копируем статус из ГПХ документа
                smz_template_name,  # Используем название СМЗ шаблона
                creation_date,  # Копируем дату создания
                rejection_reason,  # Копируем причину отклонения
                archive,  # Копируем статус архива
                instruction,  # Копируем инструкцию
                banner_shown,  # Копируем статус баннера
                date_moved_to_archive,  # Копируем дату архивации
                req_number,  # Копируем номер требования
                auto_confirmed  # Копируем статус автоподтверждения
            ))
            
            new_doc_id = cursor.fetchone()[0]
            
            # 2. Создаем записи в field_documents для каждого поля СМЗ
            smz_field_mappings = self.get_smz_field_mappings()
            
            for field_name, field_value in smz_data.items():
                if field_name in smz_field_mappings:
                    field_id = smz_field_mappings[field_name]
                    
                    cursor.execute("""
                        INSERT INTO field_documents (
                            fields_document_id,
                            template_fields_id,
                            value
                        ) VALUES (%s, %s, %s);
                    """, (
                        new_doc_id,
                        field_id,
                        str(field_value) if field_value is not None else None
                    ))
            
            self.connection.commit()
            
            print(f"   Мигрирован документ {doc_id} -> {new_doc_id}")
            print(f"   Создано {len(smz_data)} записей в field_documents")
            return True
            
        except Exception as e:
            print(f"   Ошибка миграции документа {doc_id}: {e}")
            self.connection.rollback()
            return False
    
    def preview_sql_queries(self, gph_documents: List[Tuple], smz_template_executor_id: int):
        """Предварительный просмотр всех SQL-запросов перед выполнением"""
        print(f"\nПРЕДВАРИТЕЛЬНЫЙ ПРОСМОТР SQL-ЗАПРОСОВ")
        print("=" * 60)
        
        if not gph_documents:
            print("Нет документов для миграции")
            return
        
        print(f"Будет выполнено {len(gph_documents)} операций:")
        print()
        
        for i, gph_doc in enumerate(gph_documents, 1):
            (doc_id, executor_id, template_id, status, name, creation_date, 
             rejection_reason, archive, instruction, banner_shown, date_moved_to_archive, 
             req_number, auto_confirmed) = gph_doc
            
            print(f"Операция {i}/{len(gph_documents)}")
            print(f"   Исполнитель ID: {executor_id}")
            print(f"   Исходный документ ID: {doc_id}")
            print(f"   Статус: {status}")
            print(f"   Название: {name}")
            print(f"   Дата создания: {creation_date}")
            
            # Получаем исходные данные ГПХ из field_documents
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT fd.value, tfd.name, tfd.type
                FROM field_documents fd
                JOIN template_fields_document tfd ON fd.template_fields_id = tfd.id
                WHERE fd.fields_document_id = %s
            """, (doc_id,))
            
            gph_data = {}
            for value, field_name, field_type in cursor.fetchall():
                gph_data[field_name] = value
            
            print(f"   Исходные данные ГПХ из field_documents:")
            if gph_data:
                for field_name, field_value in gph_data.items():
                    print(f"      {field_name}: {field_value}")
            else:
                print(f"      (данные не найдены)")
            
            # Показываем преобразованные данные СМЗ
            smz_data = {}
            if 'Номер' in gph_data:
                smz_data['Номер'] = gph_data['Номер']
            if 'Дата выдачи' in gph_data:
                smz_data['Дата выдачи'] = gph_data['Дата выдачи']
            if 'Дата окончания действия' in gph_data:
                smz_data['Дата окончания действия'] = gph_data['Дата окончания действия']
            smz_data['Кем выдан'] = 'Не указано (мигрировано из ГПХ)'
            
            print(f"   Преобразованные данные СМЗ:")
            for field_name, field_value in smz_data.items():
                print(f"      {field_name}: {field_value}")
            
            # Получаем маппинг полей СМЗ
            smz_field_mappings = self.get_smz_field_mappings()
            
            # Используем правильное название для СМЗ медкнижки
            smz_template_name = "Медицинская книжка/справка"
            
            # Показываем SQL-запросы
            print(f"   SQL-запросы:")
            
            # 1. INSERT в executors_document
            sql_query1 = """
                INSERT INTO executors_document (
                    executor_id,
                    template_document_id,
                    executors_document_status,
                    name,
                    creation_date,
                    rejection_reason,
                    archive,
                    instruction,
                    banner_shown,
                    date_moved_to_archive,
                    req_number,
                    auto_confirmed
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
            """
            
            print(f"      1. executors_document:")
            print(f"         {sql_query1.strip()}")
            print(f"         Параметры:")
            print(f"           executor_id: {executor_id}")
            print(f"           template_document_id: {smz_template_executor_id}")
            print(f"           executors_document_status: {status}")
            print(f"           name: {smz_template_name}")
            print(f"           creation_date: {creation_date}")
            print(f"           rejection_reason: {rejection_reason}")
            print(f"           archive: {archive}")
            print(f"           instruction: {instruction}")
            print(f"           banner_shown: {banner_shown}")
            print(f"           date_moved_to_archive: {date_moved_to_archive}")
            print(f"           req_number: {req_number}")
            print(f"           auto_confirmed: {auto_confirmed}")
            
            # 2. INSERT в field_documents для каждого поля
            print(f"      2. field_documents (будет создано {len(smz_data)} записей):")
            for field_name, field_value in smz_data.items():
                if field_name in smz_field_mappings:
                    field_id = smz_field_mappings[field_name]
                    sql_query2 = """
                        INSERT INTO field_documents (
                            fields_document_id,
                            template_fields_id,
                            value
                        ) VALUES (%s, %s, %s);
                    """
                    print(f"         Поле: {field_name}")
                    print(f"         {sql_query2.strip()}")
                    print(f"         Параметры:")
                    print(f"           fields_document_id: [НОВЫЙ ID ИЗ ПРЕДЫДУЩЕГО ЗАПРОСА]")
                    print(f"           template_fields_id: {field_id}")
                    print(f"           value: '{field_value}'")
                    print()
            
            print("=" * 60)
            print()
    
    def run_migration(self, dry_run: bool = True):
        """Запуск процесса миграции"""
        try:
            # Инициализация статистики
            self.migration_stats['start_time'] = datetime.now()
            
            # 1. Анализ структуры БД
            self.analyze_database_structure()
            
            # 2. Анализ шаблонов документов
            self.get_document_templates()
            
            # 3. Анализ полей документов
            self.get_field_mappings()
            
            # 4. Получение ГПХ документов
            gph_documents = self.get_gph_documents()
            
            if not gph_documents:
                print("\nНет ГПХ документов для миграции")
                return
            
            # Обновляем статистику
            self.migration_stats['total_documents'] = len(gph_documents)
            
            # 5. Анализ данных
            self.analyze_document_data(gph_documents)
            
            if dry_run:
                print(f"\nТЕСТОВЫЙ РЕЖИМ: Будет мигрировано {len(gph_documents)} документов")
                
                # 6. Создание template для СМЗ (только для предварительного просмотра)
                smz_template_executor_id = self.create_smz_template_executor_document()
                
                # 7. Предварительный просмотр SQL-запросов
                self.preview_sql_queries(gph_documents, smz_template_executor_id)
                
                print("   Для выполнения реальной миграции используйте --execute")
                return
            
            # 6. Создание template для СМЗ
            smz_template_executor_id = self.create_smz_template_executor_document()
            
            # 7. Миграция документов
            print(f"\nНачинаем миграцию {len(gph_documents)} документов...")
            
            success_count = 0
            failed_count = 0
            
            for i, gph_doc in enumerate(gph_documents, 1):
                print(f"   [{i}/{len(gph_documents)}] ", end="")
                if self.migrate_document(gph_doc, smz_template_executor_id):
                    success_count += 1
                else:
                    failed_count += 1
                
                # Показываем прогресс каждые 10 документов
                if i % 10 == 0:
                    print(f"   Прогресс: {i}/{len(gph_documents)} ({success_count} успешно, {failed_count} ошибок)")
            
            # Обновляем статистику
            self.migration_stats['successful_migrations'] = success_count
            self.migration_stats['failed_migrations'] = failed_count
            self.migration_stats['end_time'] = datetime.now()
            
            print(f"\nМиграция завершена: {success_count}/{len(gph_documents)} документов успешно мигрированы")
            if failed_count > 0:
                print(f"Ошибок: {failed_count}")
            
            # Показываем статистику
            self.show_migration_stats()
            
        except Exception as e:
            print(f"\nКритическая ошибка: {e}")
            raise
    
    def show_migration_stats(self):
        """Показать статистику миграции"""
        if not self.migration_stats['start_time']:
            return
        
        duration = self.migration_stats['end_time'] - self.migration_stats['start_time']
        
        print(f"\nСТАТИСТИКА МИГРАЦИИ")
        print("=" * 40)
        print(f"Всего документов: {self.migration_stats['total_documents']}")
        print(f"Успешно мигрировано: {self.migration_stats['successful_migrations']}")
        print(f"Ошибок: {self.migration_stats['failed_migrations']}")
        print(f"Пропущено: {self.migration_stats['skipped_documents']}")
        print(f"Время выполнения: {duration}")
        
        if self.migration_stats['total_documents'] > 0:
            success_rate = (self.migration_stats['successful_migrations'] / self.migration_stats['total_documents']) * 100
            print(f"Процент успеха: {success_rate:.1f}%")

def parse_arguments():
    """Парсинг аргументов командной строки"""
    parser = argparse.ArgumentParser(
        description='Массовая миграция медкнижек ГПХ в формат СМЗ',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python medical_book_migration_mass_zk.py --executors 123,456,789                    # Тестовый режим
  python medical_book_migration_mass_zk.py --executors 123,456,789 --execute          # Реальная миграция
  python medical_book_migration_mass_zk.py --executors 123,456,789 --execute --batch 50  # Пакетная обработка
  python medical_book_migration_mass_zk.py --file executor_ids.txt --execute          # Из файла
        """
    )
    
    parser.add_argument(
        '--executors', 
        type=str,
        help='Список ID исполнителей через запятую (например: 123,456,789)'
    )
    
    parser.add_argument(
        '--file',
        type=str,
        help='Файл со списком ID исполнителей (по одному на строку)'
    )
    
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Выполнить реальную миграцию (по умолчанию только тестовый режим)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Принудительно запустить в тестовом режиме'
    )
    
    parser.add_argument(
        '--batch',
        type=int,
        default=100,
        help='Размер пакета для обработки (по умолчанию 100)'
    )
    
    parser.add_argument(
        '--delay',
        type=float,
        default=0.1,
        help='Задержка между операциями в секундах (по умолчанию 0.1)'
    )
    
    return parser.parse_args()

def load_executor_ids_from_file(filename: str) -> List[int]:
    """Загрузка ID исполнителей из файла"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            ids = []
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):  # Пропускаем пустые строки и комментарии
                    try:
                        ids.append(int(line))
                    except ValueError:
                        print(f"Предупреждение: неверный ID в файле: {line}")
            return ids
    except FileNotFoundError:
        print(f"Ошибка: файл {filename} не найден")
        return []
    except Exception as e:
        print(f"Ошибка при чтении файла {filename}: {e}")
        return []

def main():
    """Главная функция"""
    print("Массовая миграция медкнижек ГПХ -> СМЗ")
    print("=" * 50)
    
    # Парсим аргументы командной строки
    args = parse_arguments()
    
    # Определяем список исполнителей
    executor_ids = None
    
    if args.executors:
        # Исполнители заданы через командную строку
        try:
            executor_ids = [int(id_str.strip()) for id_str in args.executors.split(',') if id_str.strip()]
            print(f"Исполнители из командной строки: {len(executor_ids)} ID")
            if len(executor_ids) <= 10:
                print(f"Список ID: {executor_ids}")
            else:
                print(f"Первые 10 ID: {executor_ids[:10]}...")
        except ValueError:
            print("Ошибка: неверный формат ID исполнителей")
            print("Используйте формат: --executors 123,456,789")
            return
    elif args.file:
        # Исполнители загружаются из файла
        executor_ids = load_executor_ids_from_file(args.file)
        if not executor_ids:
            return
        print(f"Исполнители из файла {args.file}: {len(executor_ids)} ID")
        if len(executor_ids) <= 10:
            print(f"Список ID: {executor_ids}")
        else:
            print(f"Первые 10 ID: {executor_ids[:10]}...")
    else:
        print("Ошибка: необходимо указать исполнителей")
        print("Используйте: --executors 123,456,789 или --file filename.txt")
        return
    
    migrator = MedicalBookMigrator(DB_CONFIG, executor_ids)
    
    try:
        migrator.connect()
        
        # Определяем режим выполнения
        dry_run = not args.execute or args.dry_run
        
        if dry_run:
            print(f"\nЗапуск в тестовом режиме...")
        else:
            print(f"\nВНИМАНИЕ: Запуск в режиме реальной миграции!")
            print(f"Будет обработано {len(executor_ids)} исполнителей")
            confirm = input("Продолжить? (yes/no): ").strip().lower()
            if confirm not in ['yes', 'y', 'да', 'д']:
                print("Миграция отменена пользователем")
                return
        
        migrator.run_migration(dry_run=dry_run)
        
    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        migrator.disconnect()

if __name__ == "__main__":
    main()
