import discord
from discord.ext import commands
import sqlite3
from datetime import datetime
from openai import OpenAI
import sys

gpt = OpenAI(api_key='[OpenAI API Key]')

prompt = {"role": "system", "content": "I am a discord bot created for the purpose of general assistance in the discord server for the YouTube channel 'Smarter Circuits'. I can use all available features of discord including emojies and code blocks, but I use the emojies sparingly. My name is Reginald."}

# Database setup
conn = sqlite3.connect('discord_bot_stats.db')
c = conn.cursor()
c.execute('''
    CREATE TABLE IF NOT EXISTS user_stats (
        user_id INTEGER PRIMARY KEY,
        display_name TEXT,
        total_messages INTEGER DEFAULT 0,
        total_words INTEGER DEFAULT 0
    )
''')
c.execute('''
    CREATE TABLE IF NOT EXISTS daily_message_counts (
        date TEXT,
        user_id INTEGER,
        display_name TEXT,
        daily_messages INTEGER DEFAULT 0,
        daily_words INTEGER DEFAULT 0,
        PRIMARY KEY (date, user_id)
    )
''')
conn.commit()

# Discord Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='', intents=intents)

async def update_or_create_user_stats(ctx, user_id, display_name, message_word_count):
    # Update or create total message stats
    c.execute('SELECT * FROM user_stats WHERE user_id = ?', (user_id,))
    result = c.fetchone()

    if result:
        total_messages, total_words = result[2], result[3]
        total_messages += 1
        total_words += message_word_count
        c.execute('UPDATE user_stats SET total_messages = ?, total_words = ?, display_name = ? WHERE user_id = ?',
                  (total_messages, total_words, display_name, user_id))
    else:
        c.execute('INSERT INTO user_stats (user_id, display_name, total_messages, total_words) VALUES (?, ?, ?, ?)',
                  (user_id, display_name, 1, message_word_count))
    conn.commit()
    await check_role_reward(ctx, user_id, total_messages=total_messages)

async def update_daily_message_counts(ctx, user_id, display_name, message_word_count):
    # Get today's date
    today = datetime.today().strftime('%Y-%m-%d')
    
    # Update or create daily message and word counts
    c.execute('SELECT * FROM daily_message_counts WHERE date = ? AND user_id = ?', (today, user_id))
    result = c.fetchone()
    daily_words = 0
    if result:
        daily_messages, daily_words = result[3], result[4]
        daily_messages += 1
        daily_words += message_word_count
        c.execute('UPDATE daily_message_counts SET daily_messages = ?, daily_words = ?, display_name = ? WHERE date = ? AND user_id = ?',
                  (daily_messages, daily_words, display_name, today, user_id))
    else:
        c.execute('INSERT INTO daily_message_counts (date, user_id, display_name, daily_messages, daily_words) VALUES (?, ?, ?, ?, ?)',
                  (today, user_id, display_name, 1, message_word_count))
    conn.commit()
    await check_role_reward(ctx, user_id, daily_words=daily_words)

async def check_role_reward(ctx, user_id, total_messages=0, daily_words=0):
    helpful_explainer_role = discord.utils.get(ctx.guild.roles, id=1237555070602711122)
    community_leader_role = discord.utils.get(ctx.guild.roles, id=1237552076037558312)
    user = ctx.guild.get_member(user_id)

    if total_messages > 500 and community_leader_role not in user.roles:
        await user.add_roles(community_leader_role)
        await ctx.send(f'{user.display_name} has posted over 500 messages! They\'ve been designated a Community Leader!')

    if daily_words > 2500 and helpful_explainer_role not in user.roles:
        await user.add_roles(helpful_explainer_role)
        await ctx.send(f'{user.display_name} has been writing a lot of words! That must mean they\'re a Helpful Explainer!')

convo = []
async def chat(ctx, id, display_name, content):
    global convo
    convo.append({"role": "user", "content": f"{display_name} says: {content}"})
    temp = [prompt] + convo
    response = gpt.chat.completions.create(
        model="gpt-4-turbo",
        messages=temp
    )
    reply = response.choices[0].message.content
    convo.append({"role": "system", "content": reply})
    await ctx.send(reply)
    size = sys.getsizeof(convo)
    while size > 100000:
        convo.pop(0)
        size = sys.getsizeof(convo)

@bot.event
async def on_ready():
    print(f'Bot {bot.user} is now online and ready!')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    print(f'received: {message.content}')
    ctx = await bot.get_context(message)
    print('got context')
    # Count words
    message_word_count = len(message.content.split())

    # Update database
    await update_or_create_user_stats(ctx, message.author.id, message.author.display_name, message_word_count)
    #print('did user stats update')
    await update_daily_message_counts(ctx, message.author.id, message.author.display_name, message_word_count)
    #print('did daily counts update')
    if message.content.lower().startswith("reginald, ") or message.content.lower().startswith("reginald "):
        print('being spoken to')
        await chat(ctx, message.author.id, message.author.display_name, message.content[10:])
        return
    print('processing commands...')
    # Process commands
    await bot.process_commands(message)
    print('and done.')

@bot.command(name='system_check')
async def system_check(ctx, user: discord.Member = None):
    await ctx.send('System working.')


@bot.command(name='stats')
async def stats(ctx, user: discord.Member = None):
    print('stats command')
    user = user or ctx.author
    c.execute('SELECT * FROM user_stats WHERE user_id = ?', (user.id,))
    result = c.fetchone()

    if result:
        avg = 0
        if result[2] > 0:
            avg = round(result[3] / result[2], 2)
        msg = f'**Stats for {result[1]}**:\n- Total Messages: {result[2]}\n- Total Words: {result[3]} (average message length: {avg})'
    else:
        msg = f'No data available for {user.display_name}.'
    print(f'sending message: {msg}')
    await ctx.send(msg)
    print('message sent')

@bot.command(name='daily_stats')
async def daily_stats(ctx, user: discord.Member = None):
    user = user or ctx.author
    today = datetime.today().strftime('%Y-%m-%d')
    c.execute('SELECT * FROM daily_message_counts WHERE date = ? AND user_id = ?', (today, user.id))
    result = c.fetchone()

    if result:
        avg = 0
        if result[3] > 0:
            avg = round(result[4] / result[3], 2)
        await ctx.send(f'**Daily Stats for {result[2]}** ({result[0]}):\n- Daily Messages: {result[3]}\n- Daily Words: {result[4]} (average message length: {avg})')
    else:
        await ctx.send(f'No data available for {user.display_name} for today.')

bot.run('[DISCORD TOKEN]')
