import sys
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout
from tinkoff.invest import  Client


#Чтение токена
with open('token.txt', 'r+') as f:
    token = f.readline()
#token = 't.cEvrJlnxDm9dMDUku9RgtZgFEaj5JcY4PwPm0t_NoPoAcL_pO7z_wx6-q3peNkw2O8LYDRsc-GAzHeuT7GWDlQ'


#Для преобразования 123.0 rub -> 123 rub
def for_price(price):
    price = price.split()
    price[0] = str(float(price[0]))
    return f'{price[0]} {price[1]}'


#Перевод типа MoneyValue в приемлемый вид (123.45 rub)
def good_money(money_value):
    value = f'{money_value.units}.{str(abs(money_value.nano))[:2]} {money_value.currency}'
    return value


#Перевод типа Quotation в приемлемый вид (12.3%)
def good_quotation(quotation):
    value = f'{quotation.units}.{str(abs(quotation.nano))[:2]}%'
    return value


#Получение name и ticker из figi
def figi_to_name(figi):
    response_figi = client.instruments.find_instrument(query=figi, api_trade_available_flag=True).instruments
    if response_figi:
        response_figi = response_figi[0]
        return {
            'name': str(response_figi.name), #Название
            'ticker': str(response_figi.ticker), #Тикер
            'figi': response_figi.figi, #ФИГИ
        }
    return {
        'name': '',
        'ticker': '',
        'figi': '',
    }


#Получение списка операций
def operations(portfolio_operations):
    return [{
        'id': oper.id, #Идентификатор операции
        'currency': oper.currency, #Валюта операции
        'payment': good_money(oper.payment), #Сумма операции
        'price': good_money(oper.price), #Цена операции за 1 инструмент
        'quantity': str(oper.quantity), #Кол-во единиц инструмента
        'date': oper.date, #Дата и время операции в формате часовом поясе UTC
        'type': oper.type, #Текстовое описание операции
        'operation_type': str(oper.operation_type), #Тип операции
    } for oper in portfolio_operations.operations if oper.quantity == 0]


#Получение позиций
def positions(portfolio_positions):
    poses = [{
        'Имя': figi_to_name(pos.figi)['name'], #Название
        'Тикер': figi_to_name(pos.figi)['ticker'], #Тикер
        'Средняя цена': for_price(good_money(pos.average_position_price)), #Средняя цена
        'Текущая цена': for_price(good_money(pos.current_price)), #Текущая цена
        'Количество': pos.quantity.units, #Количество
        'Стоимость': int(pos.quantity.units*float(good_money(pos.current_price).split()[0])), #Общая стоимость данных акций
        'Доход': int(float(good_quotation(pos.expected_yield)[:-1])), #Текущая доходность
        #'figi': figi_to_name(pos.figi)['figi'], #ФИГИ
        #'instrument_type': pos.instrument_type, #Тип
        #'current_nkd': good_money(pos.current_nkd), #НКД
    } for pos in portfolio_positions]
    return sorted(poses, key=lambda x: x['Имя'], reverse=True)


#Получение информации о счёте
def information(answer):
    return {
        'stocks_price': good_money(answer.total_amount_shares), #Стоимость акций
        'bonds_price': good_money(answer.total_amount_bonds), #Стоимость облигаций
        'etfs_price': good_money(answer.total_amount_etf), #Стоимость фондов
        'currencies_price': good_money(answer.total_amount_currencies), #Стоимость валюты
        'futures_price': good_money(answer.total_amount_futures), #Стоимость фьючерсов
        'options_price': good_money(answer.total_amount_options), #Стоимость опционов
        'total': good_money(answer.total_amount_portfolio), #Общая стоимость портфеля
        'current_id': answer.account_id, #Идентификатор счёта
        'current_positions': answer.positions, #Позиции портфеля
        'gifts': answer.virtual_positions, #Виртуальные акции в портфеле
        'relative_profitability': good_quotation(answer.expected_yield), #Относительная доходность в %
    }


#Соединение с gRPC тинькофф
with Client(token) as client:

    #Общая информация
    info = client.users.get_info() #на будущее
    tariff = info.tariff
    prem = info.prem_status
    qual = info.qual_status

    all_accounts = client.users.get_accounts().accounts #Получаем список аккаунтов
    all_portfolios = {account.name: {'id': account.id, 'type': account.type, 'open_date': account.opened_date} for account in all_accounts} #Словарь счетов

    #Работаем с каждым счётом отдельно
    for account in all_portfolios:
        curr_portfolio = information(client.operations.get_portfolio(account_id = all_portfolios[account]['id'])) #Данные о портфеле
        curr_pos = positions(curr_portfolio['current_positions']) #Данные о позициях
        curr_opers = operations(client.operations.get_operations(account_id=all_portfolios[account]['id'], state=0)) #Данные об операциях
        portfolio_total = int(float(curr_portfolio['total'].split()[0])) #Стоимость портфеля

        #Считаем сумму для каждой операции
        all_operations = {str(s):0 for s in range(64)}
        for oper in curr_opers:
            all_operations[oper['operation_type']] += abs(float(oper['payment'].split()[0]))

        input = int(all_operations['1']) #Пополнения
        output = int(all_operations['9']) #Выводы
        dividends = int(all_operations['21']) #Дивиденды
        dividends_tax = int(all_operations['8']) #Налоги по дивам
        coupons =  int(all_operations['23']) #Купоны
        coupons_tax = int(all_operations['2']) #Налоги по купонам
        comissions = int(all_operations['19']) #Комиссии брокера за сделки
        government = int(all_operations['5']) #Удержанный налог

        deposit = input-output #Чистые пополнения
        profit = portfolio_total-deposit #Прибыль
        profit_percentage = "{:.2f}".format(round(profit/deposit*100, 2))  if deposit!=0 else 0 #Абсолютный % прибыли
        clear_divs = dividends #Чистые дивиденды clear_divs = dividends - dividends_tax

#Графический интерфейс
class PortfolioApp(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("AltInvest")
        self.setGeometry(100, 100, 800, 600)

        # Создание виджетов для вывода данных
        account_label = QLabel(f"Название: {account}", self)
        total_label = QLabel(f"Стоимость портфеля: {portfolio_total} руб.", self)
        input_label = QLabel(f"Пополнения: {input} руб.", self)
        output_label = QLabel(f"Выводы: {output} руб.", self)
        deposit_label = QLabel(f"Инвестировано: {deposit} руб.", self)
        divs_label = QLabel(f"Дивиденды получено: {clear_divs} руб.", self)
        dividends_tax_label = QLabel(f"Налог по дивидендам: {dividends_tax} руб.", self)
        coupons_label = QLabel(f"Купонов получено: {coupons} руб.", self)
        coupons_tax_label = QLabel(f"Налог по купонам: {coupons_tax} руб.", self)
        comissions_label = QLabel(f"Комиссия за сделки: {comissions} руб.", self)
        government_label = QLabel(f"Удержанный налог: {government} руб.", self)
        profit_label = QLabel(f"Прибыль: {profit} руб.   ({profit_percentage}%)", self)

        # Создание таблицы
        table = QTableWidget(self)
        table.setColumnCount(7)
        table.setRowCount(len(curr_pos)+1)

        #Задаём категории таблицы (Первая строчка)
        table.setItem(0, 0, QTableWidgetItem("Имя"))
        table.setItem(0, 1, QTableWidgetItem("Тикер"))
        table.setItem(0, 2, QTableWidgetItem("Средняя цена"))
        table.setItem(0, 3, QTableWidgetItem("Текущая цена"))
        table.setItem(0, 4, QTableWidgetItem("Количество"))
        table.setItem(0, 5, QTableWidgetItem("Стоимость"))
        table.setItem(0, 6, QTableWidgetItem("Доход"))

        # Добавление данных в таблицу
        for position in enumerate(curr_pos):
            exchange = position[1]["Средняя цена"].split()[1]
            table.setItem(position[0]+1, 0, QTableWidgetItem(position[1]["Имя"]))
            table.setItem(position[0]+1, 1, QTableWidgetItem(position[1]["Тикер"]))
            table.setItem(position[0]+1, 2, QTableWidgetItem(position[1]["Средняя цена"]))
            table.setItem(position[0]+1, 3, QTableWidgetItem(position[1]["Текущая цена"]))
            table.setItem(position[0]+1, 4, QTableWidgetItem(str(position[1]["Количество"])))
            table.setItem(position[0]+1, 5, QTableWidgetItem(f'{str(position[1]["Стоимость"])} {exchange}'))
            table.setItem(position[0]+1, 6, QTableWidgetItem(f'{str(position[1]["Доход"])} {exchange}'))

        # Создание вертикального layout и добавление виджетов
        layout = QVBoxLayout()
        layout.addWidget(account_label)
        layout.addWidget(total_label)
        layout.addWidget(input_label)
        layout.addWidget(output_label)
        layout.addWidget(deposit_label)
        layout.addWidget(divs_label)
        layout.addWidget(dividends_tax_label)
        layout.addWidget(coupons_label)
        layout.addWidget(coupons_tax_label)
        layout.addWidget(comissions_label)
        layout.addWidget(government_label)
        layout.addWidget(profit_label)
        layout.addWidget(table)

        self.setLayout(layout)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PortfolioApp()
    window.show()
    sys.exit(app.exec())