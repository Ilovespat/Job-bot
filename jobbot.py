import telebot
import random
import datetime
from telebot import types
import psycopg2
import schedule
# для отправки напоминаний
# import time 


db_config={
    'dbname':'',
    'user':'',
    'password':'',
    'host':''
    }

token = ""
bot = telebot.TeleBot(token)

HELP = """
/help - вывести список команд.
/add - добавить задачу в список. Формат сообщения: дата и через пробел текст задачи:"Сегодня покормить черепаху" или "20.02 сходить к врачу").
/show - показать все добавленные задачи на указанную дату
/done - отметить задачу выполненной
/exit - выйти из программы.
/random - добавить случайную задачу на сегодня."""

RANDOM_TASKS = ["поесть", "поспать", "покормить кошку"]

def updateRecords(id):
    conn = psycopg2.connect(**db_config)
    cursor = conn.cursor()
    query = """UPDATE public.tasklist SET done=1 WHERE id=%s"""
    cursor.execute(query, (id,))
    conn.commit()
    query2 = """SELECT task FROM public.tasklist WHERE deleted = 0 AND id=%s"""
    cursor.execute(query2, (id,))
    task_name = cursor.fetchone()[0]
    text = f'Задача {task_name} № {id} выполнена'
    cursor.close()
    conn.close()
    return text

def createRecords(date, task_name):
    conn = psycopg2.connect(**db_config)
    cursor = conn.cursor()
    if date == "":
        query = """INSERT INTO public.tasklist (date_task, task, user_id) VALUES (%s,%s,%s) RETURNING id"""
        cursor.execute(query, (date, task_name, user_id,))
        id = cursor.fetchone()[0]
        conn.commit()
        text = f'Задача № {id} {task_name} добавлена'
    else:
        fdate = datetime.datetime.strptime(date, '%d.%m.%Y').date().strftime('%Y-%m-%d')
        query = """INSERT INTO public.tasklist (date_task, task, user_id) VALUES (%s,%s,%s)"""
        cursor.execute(query, (fdate, task_name, user_id,))
        conn.commit()
        query2 = """SELECT id FROM public.tasklist WHERE date_task=%s AND task=%s"""
        cursor.execute(query2, (fdate, task_name,))
        id = cursor.fetchone()[0]
        text = f'Задача № {id} {task_name} добавлена на дату {date}'
    cursor.close()
    conn.close()
    return text

def main_keyboard():
    global CLOSEKEYBOARD
    markup = types.ReplyKeyboardMarkup(resize_keyboard = True,row_width = 2)
    key1 = types.KeyboardButton('Добавить задачу')
    key2 = types.KeyboardButton('Добавить напоминание')
    key3 = types.KeyboardButton('Показать задачи') 
    key4 = types.KeyboardButton('Задача выполнена')
    key5 = types.KeyboardButton('Помощь')
    CLOSEKEYBOARD = types.ReplyKeyboardRemove()
    markup.add(key1, key2, key3, key4, key5)
    return markup

def handler_text_menu():
    @bot.message_handler(content_types = ['text'])
    def text_handler(message):
        if message.text == 'Добавить задачу':
            add_handler(message)
        if message.text == 'Добавить напоминание':
            notice_handler(message)
        if message.text == 'Показать задачи':
            show_handler(message) 
        if message.text == 'Задача выполнена':
            done(message)
        if message.text == 'Помощь':
            help(message)

@bot.message_handler(commands=["start"])
def start(message):
    if message.text == '/start':
        global chat_id
        global nameuser
        global username
        global user_id
        chat_id = message.chat.id
        nameuser = message.from_user.first_name
        username = message.from_user.username
    bot.send_message(message.chat.id, f'Привет, {nameuser}! Установи напоминание или поставь задачу', reply_markup = main_keyboard())
    handler_text_menu()
    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO public.users (name, chat_id, username) VALUES (%s, %s, %s)', (nameuser, chat_id, username,))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(e)
        cursor.close()
        conn.close()
    finally:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM public.users WHERE chat_id=%s', (str(chat_id), ))
        user_id = cursor.fetchone()[0]
        print(user_id)
        cursor.close()
        conn.close()
        schedule.every(1).minutes.do(send_notif,p = user_id)
        while True:
            schedule.run_pending()
        
@bot.message_handler(commands=["help"])
def help(message):
    bot.send_message(message.chat.id, HELP)

@bot.message_handler(commands=["add"])
def add_handler(message):
    mess = bot.send_message(message.chat.id, 'Введи дату задачи и/или ее название')
    bot.register_next_step_handler(mess, add)

def add(message):
    try:
        command = message.text.split(maxsplit=1)
        date = datetime.datetime.strptime(command[0], "%d.%m.%Y").date()
    except Exception:
        date = ""
        task_name = message.text
    else:
        date = command[0]
        task_name = command[1]
    finally:
        text = createRecords(date, task_name)
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=["notice"])
def notice_handler(message):
    mess = bot.send_message(message.chat.id, 'Введи дату 00.00.00 и время напоминания 00:00 и о чем напомнить :)', reply_markup = CLOSEKEYBOARD)
    bot.register_next_step_handler(mess, notice_add)
    
def notice_add(message):
    try:
        command = message.text.split(maxsplit=2)
        datetimestr = str(command[0]+' '+command[1])
        datetimef = datetime.datetime.strptime(datetimestr, "%d.%m.%Y %H:%M")
        note = command[2]
        text = createNotice(datetimef, note)
        bot.send_message(message.chat.id, text,reply_markup = main_keyboard())
    except Exception as e:
        print('exception',e)
        mess = bot.send_message(message.chat.id, "Ошибка ввода, попробуй еще раз.")
        bot.register_next_step_handler(mess, notice_add)
        
@bot.message_handler(commands=["show","print"])
def show_handler(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard = True,row_width = 2)
    button1 = types.KeyboardButton('На сегодня')
    button2 = types.KeyboardButton('Bсе предстоящие')
    markup.row(button1, button2)
    mess = bot.send_message(message.chat.id,'Какие задачи показать?', reply_markup=markup)
    bot.register_next_step_handler(mess, show)
    
def show(message):
    mess = message.text
    text = readRecords(mess)
    bot.send_message(message.chat.id, text, reply_markup = main_keyboard()) # не хватает возврата к главному меню

def readRecords(mess):
    conn = psycopg2.connect(**db_config)
    cursor = conn.cursor()
    text = ""
    today = datetime.date.today()
    if mess == 'На сегодня':
        query = """SELECT id, task FROM public.tasklist WHERE delete=false AND date_task = %s AND user_id =%s""" 
        cursor.execute(query,(today, user_id,))
        data_table = cursor.fetchall()
        print(data_table, type(data_table), 'readRecords data_table')
    elif mess == 'Bсе предстоящие':
        query = """SELECT id, task FROM public.tasklist WHERE delete=false AND date_task > %s AND user_id =%s""" 
        cursor.execute(query,(today,user_id,))
        data_table = cursor.fetchall()
    for task in data_table:
        id = task[0]
        task_name = task[1]
        if task[2] == 0:
            isdone = "Не сделано"
        else:
            isdone = "Сделано"
        text = text + f'№ {id} задача {task_name}' + "\n"
        print(text, type(text), 'readRecords text')
    cursor.close()
    conn.close()
    return text

def createNotice(datetimef, note):
    conn = psycopg2.connect(**db_config)
    cursor = conn.cursor()
    query = """INSERT INTO public.notifications (notify_datetime, user_id, notify_text) VALUES (%s,%s,%s) RETURNING id"""
    cursor.execute(query, (datetimef, user_id, note))
    conn.commit()
    id = cursor.fetchone()[0]
    date = datetime.datetime.strftime(datetimef,"%d.%m.%Y")
    time = datetime.datetime.strftime(datetimef,"%H:%M")
    text = f'Напоминание № {id} {note} добавлено на дату {date} время {time}'
    cursor.close()
    conn.close()
    return text
    
@bot.message_handler(commands=["random"])
def random_add(message):
    date = ""
    task = random.choice(RANDOM_TASKS)
    add_todo(date,task)
    text = "Задача "+ task + " добавлена на дату " + date
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=["done"])
def done(message):
    dones = message.text.split(maxsplit=1)
    id = dones[1]
    text = updateRecords(int(id))
    bot.send_message(message.chat.id, text)

# Отправка напоминаний
# def send_notif():
#     conn = psycopg2.connect(**db_config)
#     cursor = conn.cursor()
#     query = """SELECT notifications.notify_datetime, notifications.notify_text, notifications.id, users.chat_id FROM public.notifications AS notifications INNER JOIN public.users AS users ON notifications.user_id = users.id WHERE notifications.notify_datetime < now() AND notifications.show = false"""
#     cursor.execute(query,)
#     notif = cursor.fetchall()
#     for i in notif:
#         bot.send_message(i[3],f'Напоминание {i[1]}')
#         query = """UPDATE public.notifications SET show = true WHERE id = %s"""
#         cursor.execute(query, (i[2],))
#     conn.commit()
#     cursor.close()
#     conn.close()

bot.polling(none_stop=True)

