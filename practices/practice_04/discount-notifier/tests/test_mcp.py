"""Real SDK client/server subprocesses over stdio; all databases are temporary."""
import asyncio
import hashlib
import os
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest
from mcp import Client
from mcp.client.stdio import StdioServerParameters

from app import storage
from app.service import generate_notifications,preview_notifications
from app.source import collect_snapshots

ROOT=Path(__file__).resolve().parents[1]
NOW='2026-10-07T12:00:00+03:00'


def prepare():
    collected=collect_snapshots(ROOT/'research/snapshots')
    assert collected['complete'] and not collected['errors']
    storage.import_promotions(collected['promotions'],complete=True)
    storage.set_city('Санкт-Петербург')
    storage.subscribe('rostics',True)


def parameters():
    return StdioServerParameters(command=sys.executable,args=[str(ROOT/'scripts/mcp_server.py')],
        cwd='/tmp',env={'APP_DB_PATH':str(storage.database_path()),'APP_BACKGROUND':'0'})


def database_snapshot():
    path=storage.database_path()
    files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in path.parent.iterdir() if p.is_file()}
    with sqlite3.connect(path.resolve().as_uri()+'?mode=ro&immutable=1',uri=True) as conn:
        dump=list(conn.iterdump())
        version=conn.execute('PRAGMA schema_version').fetchone()[0]
    return files,dump,version


def run(coroutine):
    return asyncio.run(asyncio.wait_for(coroutine,timeout=30))


def test_stdio_preview_and_invalid_arguments():
    prepare()
    expected=preview_notifications(datetime.fromisoformat(NOW),read_only=True)
    assert len(expected['notifications'])==7
    assert len(expected['notifications'])+len(expected['excluded'])==13
    before=database_snapshot()

    async def scenario():
        # legacy explicitly sends initialize + initialized, as OpenCode 1.18 does.
        async with Client(parameters(),mode='legacy',read_timeout_seconds=10) as client:
            assert client.server_info.name=='discount-notifier'
            assert client.protocol_version
            tools=(await client.list_tools()).tools
            assert [tool.name for tool in tools]==['preview_notifications']
            assert tools[0].input_schema['additionalProperties'] is False
            assert tools[0].annotations.read_only_hint
            for _ in range(2):
                result=await client.call_tool('preview_notifications',{'now':NOW})
                assert not result.is_error
                data=result.structured_content
                assert {k:data[k] for k in expected}==expected
                assert 'без онлайн-обновления' in data['explanation']
                assert 'создания уведомлений' in data['explanation']
            bad_arguments=[({'now':123},'строкой'),({'now':True},'строкой'),
                ({'now':None},'строкой'),({'now':[]},'строкой'),
                ({'now':'2026-02-30T12:00:00+03:00'},'неверная дата'),
                ({'now':'not-a-date'},'неверная дата'),
                ({'now':'2026-10-07T12:00:00'},'часовой пояс'),
                ({'now':NOW,'APP_DB_PATH':'/tmp/other.db'},'дополнительные поля'),
                ({'user_id':'invented'},'дополнительные поля')]
            for args,message in bad_arguments:
                result=await client.call_tool('preview_notifications',args)
                assert result.is_error and message in result.content[0].text
                recovery=await client.call_tool('preview_notifications',{'now':NOW})
                assert not recovery.is_error and recovery.structured_content['notifications']==expected['notifications']
            started=datetime.now().astimezone()
            current=await client.call_tool('preview_notifications',{})
            ended=datetime.now().astimezone()
            assert not current.is_error
            assert started<=datetime.fromisoformat(current.structured_content['checked_at'])<=ended
            utc=await client.call_tool('preview_notifications',{'now':'2026-10-07T09:00:00Z'})
            assert not utc.is_error and utc.structured_content['notifications']==expected['notifications']
    run(scenario())
    assert database_snapshot()==before  # Includes bytes, all tables, schema, and no new sidecars.
    assert not storage.read_state(read_only=True)['notifications']


def test_stdio_missing_database_recovery_without_creation():
    path=storage.database_path()
    async def scenario():
        async with Client(parameters(),mode='legacy',read_timeout_seconds=10) as client:
            result=await client.call_tool('preview_notifications',{'now':NOW})
            assert result.is_error and 'База не существует' in result.content[0].text
            assert not path.exists() and not list(path.parent.glob(path.name+'*'))
            prepare()  # Explicit operation outside server/tool, server remains alive.
            result=await client.call_tool('preview_notifications',{'now':NOW})
            assert not result.is_error and len(result.structured_content['notifications'])==7
    run(scenario())


def test_stdio_invalid_schema_and_live_wal_are_not_modified():
    path=storage.database_path()
    with sqlite3.connect(path) as conn:
        conn.execute('CREATE TABLE unrelated(x)')
    before=database_snapshot()
    async def invalid_schema():
        async with Client(parameters(),mode='legacy',read_timeout_seconds=10) as client:
            result=await client.call_tool('preview_notifications',{})
            assert result.is_error and 'no such table' in result.content[0].text
    run(invalid_schema())
    assert database_snapshot()==before
    prepare()
    with storage.connection() as writer:
        writer.execute('UPDATE preferences SET city=? WHERE id=1',('Москва',))
        writer.commit()
        before=database_snapshot()
        async def live_wal():
            async with Client(parameters(),mode='legacy',read_timeout_seconds=10) as client:
                result=await client.call_tool('preview_notifications',{'now':NOW})
                assert result.is_error and 'База имеет WAL' in result.content[0].text
        run(live_wal())
        assert database_snapshot()==before


def test_stdio_existing_notifications_read_flags_and_preferences_preserved():
    prepare()
    assert generate_notifications(datetime.fromisoformat(NOW))==7
    notes=storage.read_state()['notifications']
    storage.mark_read(notes[0]['id'])
    before=database_snapshot()
    async def scenario():
        async with Client(parameters(),mode='legacy',read_timeout_seconds=10) as client:
            result=await client.call_tool('preview_notifications',{'now':NOW})
            assert not result.is_error
            data=result.structured_content
            assert data['city']=='Санкт-Петербург' and data['subscriptions']==['rostics']
            assert data['notifications']==[]
            assert sum(p['reason']=='Уведомление уже создано' for p in data['excluded'])==7
    run(scenario())
    assert database_snapshot()==before


def test_readonly_connection_rejects_writes_and_does_not_bootstrap_profile():
    prepare()
    before=database_snapshot()
    with storage.readonly_connection() as conn:
        with pytest.raises(sqlite3.OperationalError,match='readonly'):
            conn.execute('UPDATE preferences SET city="Changed"')
        with pytest.raises(sqlite3.OperationalError,match='readonly'):
            conn.execute('CREATE TABLE injected(x)')
    assert database_snapshot()==before
    with storage.connection() as conn:
        conn.execute('DELETE FROM preferences')
    before=database_snapshot()
    with pytest.raises(ValueError,match='отсутствует локальный профиль'):
        storage.read_state(read_only=True)
    assert database_snapshot()==before


def test_mcp_import_starts_no_web_background_or_database():
    path=storage.database_path()
    result=subprocess.run([sys.executable,'-c',
        "import sys; import app.mcp_server; assert 'app.main' not in sys.modules; "
        "assert 'fastapi' not in sys.modules"],cwd=ROOT,env=os.environ.copy(),
        capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
    assert result.stdout=='' and not path.exists()
