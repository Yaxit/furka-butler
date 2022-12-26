from telegram import ForceReply, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters


# Define some helper functions
def remove_job_if_exists(name: str, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Remove job with given name. Returns whether job was removed."""
    current_jobs = context.job_queue.get_jobs_by_name(name)
    if not current_jobs:
        return False
    for job in current_jobs:
        job.schedule_removal()
    return True


# Define a few command handlers. These usually take the two arguments update and
# context.
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_text("Guten Tag, Sir.")


async def alarm(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send the alarm message."""
    job = context.job
    data = job.data
    person = data['people'].pop(0)
    data['people'].append(person)

    msg = f"""Guten Tag {person}!
    The task {data['name']} requires your attention!"""
    await context.bot.send_message(job.chat_id, text=msg)


async def remove_chore(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove the job if the user changed their mind."""
    chat_id = update.message.chat_id
    chore_name = str(context.args[0])
    job_removed = remove_job_if_exists(chore_name, context)
    text = "Timer successfully cancelled!" if job_removed else "You have no active timer."
    await update.message.reply_text(text)


async def add_chore(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    #TODO better syntax check and error handling
    """Add a repeating task"""
    hint_string = "Usage: /add_task <name> <periodicity> <[list of people]>"
    chat_id = update.effective_message.chat_id
    try:
        chore_name = str(context.args[0])
        chore_interval = float(context.args[1])
        chore_users = context.args[2:]
    except ValueError:
        await update.effective_message.reply_text(hint_string)

    task_data = {
        'name': chore_name,
        'interval': chore_interval,
        'people': chore_users
    }

    try:    #TODO maybe remove
        if chore_interval < 2:
            await update.effective_message.reply_text("Nein, zu viel!")
            return

        job_removed = remove_job_if_exists(chore_name, context)
        context.job_queue.run_repeating(alarm, interval=chore_interval, name=chore_name, chat_id=chat_id, data=task_data)

        text = f"Task {chore_name} scheduled successfully!"
        if job_removed:
            text += " The old one was removed."
        await update.effective_message.reply_text(text)

    except (IndexError, ValueError):
        await update.effective_message.reply_text(hint_string)


async def get_chores(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Print a list of all scheduled tasks"""
    chat_id = update.effective_message.chat_id
    jobs = context.job_queue.jobs()
    msg = [f"{j.name} - interval:{j.data}" for j in jobs]
    msg = '\n'.join(msg)
    msg = 'Scheduled tasks\n' + msg

    await context.bot.send_message(chat_id, text=msg)


def main() -> None:
    """Start the bot."""

    with open('TOKEN.txt', 'r') as f:
        TOKEN = f.readline().strip()
    print(TOKEN)

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TOKEN).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("set", add_chore))
    application.add_handler(CommandHandler("unset", remove_chore))
    application.add_handler(CommandHandler("list", get_chores))
    # on non command i.e message - echo the message on Telegram
    # application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # Run the bot until the user presses Ctrl-C
    application.run_polling()


if __name__ == '__main__':
    main()