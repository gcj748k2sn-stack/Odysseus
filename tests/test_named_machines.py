"""Configured machine names for the agent's named-machine check
(src/named_machines.py; docs/todo.md item 27, fix b)."""
import json
import os

import pytest

import src.named_machines as nm


def _cookbook(path, servers):
    path.write_text(json.dumps({"env": {"servers": servers, "remoteHost": ""}}), encoding="utf-8")
    return str(path)


def test_cookbook_names_and_hosts(tmp_path):
    p = _cookbook(tmp_path / "cookbook_state.json", [
        {"name": "Local", "host": ""},
        {"name": "GPU Box", "host": "cedrik@gpu-box.lan:22"},
        {"name": "pi", "host": "192.168.0.50"},
        {"name": None, "host": 7},
        "not a dict",
    ])
    assert nm.cookbook_machine_names(p) == {"GPU Box", "cedrik@gpu-box.lan", "gpu-box.lan", "pi", "192.168.0.50"}


def test_cookbook_with_only_local_names_nothing(tmp_path):
    """This Mac on 2026-10-04: one server, "Local", host ''."""
    assert nm.cookbook_machine_names(_cookbook(tmp_path / "c.json", [{"name": "Local", "host": ""}])) == set()


def test_ssh_aliases(tmp_path):
    p = tmp_path / "config"
    p.write_text(
        "# comment\n"
        "Host mediaserver nas\n"
        "  HostName 192.168.0.20\n"
        "  User cedrik\n"
        "Host=gpu-box\n"
        "Host *.lan !bad nas?\n"
        "Host *\n"
        "  ServerAliveInterval 30\n"
        "Include ~/.ssh/other\n"
        "host \"quoted\"\n",
        encoding="utf-8",
    )
    assert nm.ssh_config_aliases(str(p)) == {"mediaserver", "nas", "gpu-box", "quoted"}


def test_missing_and_malformed_files_name_nothing(tmp_path):
    bad = tmp_path / "c.json"
    bad.write_text("{not json", encoding="utf-8")
    assert nm.configured_machine_names(str(bad), str(tmp_path / "absent")) == frozenset()
    assert nm.configured_machine_names("", "") == frozenset()


def test_names_follow_file_changes(tmp_path):
    ssh = tmp_path / "config"
    ssh.write_text("Host alpha\n", encoding="utf-8")
    cb = _cookbook(tmp_path / "c.json", [])
    assert nm.configured_machine_names(cb, str(ssh)) == {"alpha"}
    ssh.write_text("Host beta\n", encoding="utf-8")
    st = os.stat(ssh)
    os.utime(ssh, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))
    assert nm.configured_machine_names(cb, str(ssh)) == {"beta"}
    os.remove(ssh)
    assert nm.configured_machine_names(cb, str(ssh)) == frozenset()


NAMES = frozenset({"mediaserver", "GPU Box", "gpu-box.lan", "192.168.0.50"})


@pytest.mark.parametrize("text", [
    "list files on mediaserver",
    "list files on MediaServer.",
    "download qwen3 on the gpu box",
    "download qwen3 on gpu-box",
    "copy the logs from gpu-box.lan",
    "read the sensor from 192.168.0.50",
])
def test_mentions(text):
    assert nm.mentions_named_machine(text, NAMES)


@pytest.mark.parametrize("text", [
    "list files on mediaservers",
    "copy the logs from gpu-box.lan.example",
    "read the sensor from 192.168.0.501",
    "data from http://192.168.0.50",   # a URL is a web address, not a machine
    "the mediaserver is slow",         # named, but not "on/from" it
    "a report on climate change",
    "",
])
def test_does_not_mention(text):
    assert not nm.mentions_named_machine(text, NAMES)


def test_no_names_never_matches():
    assert not nm.mentions_named_machine("list files on mediaserver", ())
