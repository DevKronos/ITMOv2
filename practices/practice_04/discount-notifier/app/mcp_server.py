"""One local, read-only MCP tool. Importing this module starts no application jobs."""
import asyncio
import json
import logging
import sqlite3
from datetime import datetime

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool, ToolAnnotations

from app import service
from app.domain import TZ

NOTICE = ('Предпросмотр сохранённых данных одного локального профиля: без онлайн-обновления, '
          'создания уведомлений и отправки сообщений. Даты и территория не дополняются догадками.')
TOOL = Tool(
    name='preview_notifications',
    description=NOTICE+' Показывает город, подписки, кандидатов и причины исключения.',
    input_schema={
        'type':'object',
        'properties':{'now':{'type':'string','format':'date-time',
            'description':'Необязательно: ISO 8601 с часовым поясом; только для этого вызова.'}},
        'additionalProperties':False,
    },
    annotations=ToolAnnotations(read_only_hint=True,destructive_hint=False,
                                idempotent_hint=True,open_world_hint=False),
)


async def list_tools(ctx,params):
    return ListToolsResult(tools=[TOOL])


def parse_now(arguments):
    if not isinstance(arguments,dict): raise ValueError('Аргументы должны быть объектом')
    if set(arguments)-{'now'}: raise ValueError('Поддерживается только поле now; дополнительные поля запрещены')
    if 'now' not in arguments: return datetime.now(TZ)
    value=arguments['now']
    if not isinstance(value,str): raise ValueError('now должен быть строкой ISO 8601 с часовым поясом')
    try: instant=datetime.fromisoformat(value)
    except ValueError as exc: raise ValueError('now: неверная дата ISO 8601') from exc
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError('now должен содержать часовой пояс, например +03:00 или Z')
    return instant


async def call_tool(ctx,params):
    try:
        if params.name!=TOOL.name: raise ValueError('Неизвестный инструмент')
        instant=parse_now(params.arguments if params.arguments is not None else {})
        result=service.preview_notifications(instant,read_only=True)
        result['explanation']=NOTICE
        return CallToolResult(content=[TextContent(type='text',text=json.dumps(result,ensure_ascii=False))],
                              structured_content=result)
    except (ValueError,TypeError,KeyError,OSError,sqlite3.Error) as exc:
        return CallToolResult(is_error=True,content=[TextContent(type='text',text=f'Предпросмотр недоступен: {exc}')])


server=Server('discount-notifier',version='1.0.0',instructions=NOTICE,
              on_list_tools=list_tools,on_call_tool=call_tool)


async def serve():
    async with stdio_server() as (read,write):
        await server.run(read,write,server.create_initialization_options())


def main():
    logging.basicConfig(level=logging.WARNING)  # logging defaults to stderr; stdout is protocol only.
    asyncio.run(serve())


if __name__=='__main__': main()
