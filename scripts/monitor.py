"""
Скрипт для мониторинга производительности системы
"""
import psutil
import time
import sqlite3
import os
import logging
from datetime import datetime, timedelta
import json

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class SystemMonitor:
    """Мониторинг системных ресурсов"""
    
    def __init__(self, db_path="bot_database.db"):
        self.db_path = db_path
        self.monitoring_data = []
    
    def get_system_stats(self):
        """Получение системной статистики"""
        try:
            # CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            # Память
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_available = memory.available / (1024**3)  # GB
            
            # Диск
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            disk_free = disk.free / (1024**3)  # GB
            
            # Сеть
            network = psutil.net_io_counters()
            
            # Процессы
            process_count = len(psutil.pids())
            
            stats = {
                'timestamp': datetime.now().isoformat(),
                'cpu_percent': cpu_percent,
                'cpu_count': cpu_count,
                'memory_percent': memory_percent,
                'memory_available_gb': round(memory_available, 2),
                'disk_percent': disk_percent,
                'disk_free_gb': round(disk_free, 2),
                'network_bytes_sent': network.bytes_sent,
                'network_bytes_recv': network.bytes_recv,
                'process_count': process_count
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting system stats: {e}")
            return None
    
    def get_database_stats(self):
        """Получение статистики базы данных"""
        try:
            if not os.path.exists(self.db_path):
                return None
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Размер базы данных
            db_size = os.path.getsize(self.db_path) / (1024**2)  # MB
            
            # Количество записей в таблицах
            cursor.execute("SELECT COUNT(*) FROM users")
            users_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM subscriptions")
            subscriptions_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM admin_users")
            admin_users_count = cursor.fetchone()[0]
            
            # Активные подписки
            cursor.execute("SELECT COUNT(*) FROM subscriptions WHERE is_active = 1")
            active_subscriptions = cursor.fetchone()[0]
            
            # Пользователи за последние 24 часа
            yesterday = datetime.now() - timedelta(days=1)
            cursor.execute(
                "SELECT COUNT(*) FROM users WHERE registration_date > ?",
                (yesterday,)
            )
            new_users_24h = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                'db_size_mb': round(db_size, 2),
                'users_count': users_count,
                'subscriptions_count': subscriptions_count,
                'admin_users_count': admin_users_count,
                'active_subscriptions': active_subscriptions,
                'new_users_24h': new_users_24h
            }
            
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return None
    
    def get_telegram_bot_stats(self):
        """Получение статистики Telegram бота"""
        try:
            # Здесь можно добавить логику для получения статистики бота
            # Например, количество активных пользователей, сообщений и т.д.
            return {
                'bot_status': 'active',  # В реальном приложении проверять статус
                'last_activity': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting bot stats: {e}")
            return None
    
    def collect_all_stats(self):
        """Сбор всей статистики"""
        stats = {
            'timestamp': datetime.now().isoformat(),
            'system': self.get_system_stats(),
            'database': self.get_database_stats(),
            'telegram_bot': self.get_telegram_bot_stats()
        }
        
        self.monitoring_data.append(stats)
        
        # Ограничиваем количество записей в памяти
        if len(self.monitoring_data) > 1000:
            self.monitoring_data = self.monitoring_data[-1000:]
        
        return stats
    
    def save_stats_to_file(self, filename=None):
        """Сохранение статистики в файл"""
        if filename is None:
            filename = f"monitoring_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.monitoring_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Stats saved to {filename}")
            return filename
        except Exception as e:
            logger.error(f"Error saving stats to file: {e}")
            return None
    
    def generate_report(self):
        """Генерация отчета по производительности"""
        if not self.monitoring_data:
            return "Нет данных для анализа"
        
        try:
            # Анализируем последние 24 часа
            day_ago = datetime.now() - timedelta(days=1)
            recent_data = [
                stat for stat in self.monitoring_data
                if datetime.fromisoformat(stat['timestamp']) > day_ago
            ]
            
            if not recent_data:
                return "Нет данных за последние 24 часа"
            
            # Анализ CPU
            cpu_values = [stat['system']['cpu_percent'] for stat in recent_data if stat['system']]
            avg_cpu = sum(cpu_values) / len(cpu_values) if cpu_values else 0
            max_cpu = max(cpu_values) if cpu_values else 0
            
            # Анализ памяти
            memory_values = [stat['system']['memory_percent'] for stat in recent_data if stat['system']]
            avg_memory = sum(memory_values) / len(memory_values) if memory_values else 0
            max_memory = max(memory_values) if memory_values else 0
            
            # Анализ диска
            disk_values = [stat['system']['disk_percent'] for stat in recent_data if stat['system']]
            avg_disk = sum(disk_values) / len(disk_values) if disk_values else 0
            max_disk = max(disk_values) if disk_values else 0
            
            report = f"""
=== ОТЧЕТ ПО ПРОИЗВОДИТЕЛЬНОСТИ ===
Период: последние 24 часа
Количество измерений: {len(recent_data)}

СИСТЕМНЫЕ РЕСУРСЫ:
CPU:
  - Среднее использование: {avg_cpu:.1f}%
  - Максимальное использование: {max_cpu:.1f}%

Память:
  - Среднее использование: {avg_memory:.1f}%
  - Максимальное использование: {max_memory:.1f}%

Диск:
  - Среднее использование: {avg_disk:.1f}%
  - Максимальное использование: {max_disk:.1f}%

БАЗА ДАННЫХ:
"""
            
            # Добавляем статистику БД если есть
            if recent_data[-1].get('database'):
                db_stats = recent_data[-1]['database']
                report += f"""
  - Размер БД: {db_stats['db_size_mb']} MB
  - Пользователей: {db_stats['users_count']}
  - Подписок: {db_stats['subscriptions_count']}
  - Активных подписок: {db_stats['active_subscriptions']}
  - Новых пользователей за 24ч: {db_stats['new_users_24h']}
"""
            
            report += f"""
РЕКОМЕНДАЦИИ:
"""
            
            # Рекомендации по CPU
            if avg_cpu > 80:
                report += "- ⚠️ Высокое использование CPU. Рассмотрите оптимизацию кода или увеличение ресурсов\n"
            elif avg_cpu > 60:
                report += "- ⚠️ Среднее использование CPU. Мониторьте тенденции\n"
            else:
                report += "- ✅ Использование CPU в норме\n"
            
            # Рекомендации по памяти
            if avg_memory > 80:
                report += "- ⚠️ Высокое использование памяти. Проверьте утечки памяти\n"
            elif avg_memory > 60:
                report += "- ⚠️ Среднее использование памяти. Мониторьте тенденции\n"
            else:
                report += "- ✅ Использование памяти в норме\n"
            
            # Рекомендации по диску
            if avg_disk > 90:
                report += "- ⚠️ Критическое использование диска. Освободите место\n"
            elif avg_disk > 80:
                report += "- ⚠️ Высокое использование диска. Рассмотрите очистку\n"
            else:
                report += "- ✅ Использование диска в норме\n"
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return f"Ошибка при генерации отчета: {e}"
    
    def start_monitoring(self, interval=60, duration=None):
        """Запуск мониторинга"""
        logger.info(f"Starting monitoring with {interval}s interval")
        
        start_time = time.time()
        iteration = 0
        
        try:
            while True:
                iteration += 1
                current_time = time.time()
                
                # Сбор статистики
                stats = self.collect_all_stats()
                logger.info(f"Iteration {iteration}: CPU {stats['system']['cpu_percent']}%, "
                          f"Memory {stats['system']['memory_percent']}%")
                
                # Проверка условий остановки
                if duration and (current_time - start_time) > duration:
                    logger.info("Monitoring duration reached, stopping")
                    break
                
                # Ожидание до следующего измерения
                time.sleep(interval)
                
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
        except Exception as e:
            logger.error(f"Monitoring error: {e}")
        finally:
            # Сохраняем статистику и генерируем отчет
            filename = self.save_stats_to_file()
            report = self.generate_report()
            
            print("\n" + "="*50)
            print("МОНИТОРИНГ ЗАВЕРШЕН")
            print("="*50)
            print(f"Статистика сохранена в: {filename}")
            print(report)


def main():
    """Главная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(description='System Performance Monitor')
    parser.add_argument('--interval', type=int, default=60, 
                       help='Monitoring interval in seconds (default: 60)')
    parser.add_argument('--duration', type=int, default=None,
                       help='Monitoring duration in seconds (default: unlimited)')
    parser.add_argument('--db-path', type=str, default='bot_database.db',
                       help='Path to database file (default: bot_database.db)')
    
    args = parser.parse_args()
    
    monitor = SystemMonitor(args.db_path)
    monitor.start_monitoring(args.interval, args.duration)


if __name__ == "__main__":
    main()
