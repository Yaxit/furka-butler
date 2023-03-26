import logging
from datetime import timedelta
from apscheduler.triggers.combining import AndTrigger, OrTrigger
from typing import List

from telegram import ForceReply, Update, User
from telegram.ext import Application, CommandHandler, StringCommandHandler, StringRegexHandler, ConversationHandler, ContextTypes, MessageHandler, filters

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

class Assignee():
    def __init__(self, user:str) -> None:
        self.user = user
        self.duties = 0

    def __repr__(self) -> str:
        return self.user + f"[{self.duties}]"


class Task():
    def __init__(self, name:str) -> None:
        self.name = name
        self.description = None
        self.trigger = None
        self.schedule = None
        self.assignees = []

    def update_description(self, description:str) -> None:
        self.description = description

    def add_assignee(self, assignee:Assignee) -> None:
        self.assignees.append(assignee)

    def remove_assignee(self, assignee:Assignee) -> None:
        self.assignees.remove(assignee)

    def update_schedule(self, schedule:str) -> None:
        self.schedule = schedule

    def __repr__(self) -> str:
        return f"{self.name}/{self.triggerdays}/{[a for a in self.assignees]}" #TODO remove assignees once debugged


async def init(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""

    context.chat_data['tasks'] = dict()
    # normal message
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Guten Tag, {update.effective_user.name}."
    )
    # TODO: add help message/instructions


async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add a job to the queue."""
    task_name = context.args[0]
    trigger = {
        'trigger': 'cron',
        'second': '*/5',
    }
    context.chat_data['tasks'] = {task_name:Task(task_name)}


# async def edit_task_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
#     """Modify a job"""
#     context.chat_data['tasks']

async def start_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    task = context.chat_data['tasks'][context.args[0]]
    context.job_queue.run_custom(alarm, data="test", job_kwargs=task.trigger, chat_id=update.effective_chat.id)
    await update.message.reply_text('Timer successfully set!')


async def alarm(context) -> None:
    """Send the alarm message."""
    await context.bot.send_message(chat_id=context.job.chat_id, text='Beep!')

# conversation callbacks
ADD_DESC, ADD_TRIGGER, ADD_ASSIGNEES, CONFIRM = range(4)
END = ConversationHandler.END

async def conv0_add_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the conversation and ask the user about the chore to add."""
    task_name = context.args[0]
    context.chat_data['wip_task'] = Task(task_name)
    await update.message.reply_text(
        f'New Task: {task_name}\n'+
        f'Please add a description for the task, or type /skip if you don\'t want to.',
        reply_markup=ForceReply(selective=True),
    )
    return ADD_DESC

async def conv1_add_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Add description."""
    context.chat_data['wip_task'].description = update.message.text
    await update.message.reply_text(
        'Please provide the periodicity of the task (supported formats: cron).',
        reply_markup=ForceReply(selective=True),
    )
    return ADD_TRIGGER

async def conv1_skip_desk(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Skips the description"""
    await update.message.reply_text(
        'No description added (u lazy boi)\n'+
        'Please provide the periodicity of the task.',
        reply_markup=ForceReply(selective=True),
    )
    return ADD_TRIGGER

async def conv2_add_trigger(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Add the interval/trigger for the task."""
    f = update.message.text
    context.chat_data['wip_task'].trigger = f
    # TODO implement cron parsing
    context.chat_data['wip_task'].trigger = {
    'trigger': 'cron',
    'second': '*/5',
}
    # TODO parse trigger and print result
    await update.message.reply_text(
        f'Setting up trigger: {f}\n'+
        f'Please add the people responsible for the task.',
        reply_markup=ForceReply(selective=True),
    )
    return ADD_ASSIGNEES

async def conv3_add_people(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Add the people responsible for the task."""
    # TODO investigate MessageEntity.TEXT_MENTION,MessageEntity.MENTION
    # TODO make assignees objects from mentions
    f = update.message.text
    context.chat_data['wip_task'].assignees.append(f)
    await update.message.reply_text(
        f'Task ready to release: {f}'+
        f'{context.chat_data["wip_task"]}'+
        f'Please confirm the task with /confirm or cancel with /cancel.',
        reply_markup=ForceReply(selective=True),
    )
    return CONFIRM

async def conv4_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Confirm and save the task."""
    # add task to chat_data
    # todo copy data to avoid reference issues
    context.chat_data['tasks'][context.chat_data['wip_task'].name] = context.chat_data['wip_task']
    task = context.chat_data['wip_task']
    await update.message.reply_text(
        f'Task confirmed and scheduled.',
    )
    context.job_queue.run_custom(alarm, data="test", job_kwargs=task.trigger, chat_id=update.effective_chat.id)
    context.chat_data['wip_task'] = None

    return END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation."""
    await update.message.reply_text('Task Canceled')
    return END


def main() -> None:
    """Start the bot."""

    with open('TOKEN.txt', 'r') as f:
        TOKEN = f.readline().strip()

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TOKEN).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("init", init))
    application.add_handler(ConversationHandler(
        entry_points=[CommandHandler('add_task', conv0_add_task)],
        states={
            ADD_DESC: [MessageHandler(filters.ALL & ~ filters.COMMAND, conv1_add_desc),
                       CommandHandler('skip', conv1_skip_desk)],
            ADD_TRIGGER: [MessageHandler(filters.ALL & ~ filters.COMMAND, conv2_add_trigger)],
            ADD_ASSIGNEES: [MessageHandler(filters.ALL & ~ filters.COMMAND, conv3_add_people)],
            CONFIRM: [CommandHandler('confirm', conv4_confirm)]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    ))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(poll_interval=0.0) #TODO increase poll interval


if __name__ == '__main__':
    main()