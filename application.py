import atexit
import json
import os
import subprocess
from pathlib import Path

import dearpygui.dearpygui as dpg


class TunnelingToolApplication:
    config_path = Path(os.getenv('APPDATA')) / 'ssh_tunneling_tool' / 'ssh_tunnels.json'
    tunnels = {}

    def load_tunnels(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                self.tunnels = {tunnel['name']: tunnel for tunnel in json.load(f)}
        else:
            self.tunnels = {}

    def save_tunnels(self):
        os.makedirs(self.config_path.parent, exist_ok=True)
        serializable_fields = ['name', 'host', 'local_port', 'remote_port', 'jump_host', 'jump_username',
                               'remote_username', 'ssh_key']
        with open(self.config_path, 'w') as f:
            serialized_tunnels = [{key: tunnel[key] for key in serializable_fields} for tunnel in self.tunnels.values()]
            json.dump(serialized_tunnels, f, indent=4)

    def add_tunnel(self, sender, app_data, user_data):
        tunnel_name = dpg.get_value('name_input')

        tunnel_data = {
            'name': tunnel_name,
            'host': dpg.get_value('host_input'),
            'local_port': dpg.get_value('local_port_input'),
            'remote_port': dpg.get_value('remote_port_input'),
            'jump_host': dpg.get_value('jump_host_input') or None,
            'jump_username': dpg.get_value('jump_username_input') or None,
            'remote_username': dpg.get_value('remote_username_input'),
            'ssh_key': dpg.get_value('ssh_key_input'),
            'enabled': False
        }
        self.tunnels[tunnel_name] = tunnel_data

        self.save_tunnels()
        self.update_tunnel_list()
        dpg.set_value('add_button', 'Add Tunnel')

    def delete_tunnel(self, sender, app_data, user_data):
        if user_data in self.tunnels:
            del self.tunnels[user_data]
            self.save_tunnels()
            self.update_tunnel_list()

    def enable_tunnel(self, sender, app_data, user_data):
        tunnel = self.tunnels.get(user_data)
        if tunnel:
            tunnel['enabled'] = True
            # Start the SSH tunnel using subprocess
            command = f"ssh -i {tunnel['ssh_key']} "
            if tunnel['jump_host'] and tunnel['jump_username']:
                command += f" -J {tunnel['jump_username']}@{tunnel['jump_host']} "
            command += f"-N -L {tunnel['local_port']}:localhost:{tunnel['remote_port']} " \
                       f"{tunnel['remote_username']}@{tunnel['host']}"

            print("Executing Command:" + command)
            process = subprocess.Popen(command, creationflags=subprocess.CREATE_NO_WINDOW)
            tunnel['process'] = process

        self.update_tunnel_list()

    def select_tunnel(self, sender, app_data, user_data):
        tunnel = self.tunnels.get(user_data)
        if tunnel:
            dpg.set_value('name_input', tunnel['name'])
            dpg.set_value('host_input', tunnel['host'])
            dpg.set_value('local_port_input', tunnel['local_port'])
            dpg.set_value('remote_port_input', tunnel['remote_port'])
            dpg.set_value('jump_host_input', tunnel['jump_host'] or '')
            dpg.set_value('jump_username_input', tunnel['jump_username'] or '')
            dpg.set_value('remote_username_input', tunnel['remote_username'])
            dpg.set_value('ssh_key_input', tunnel['ssh_key'])
            dpg.set_item_label('add_button', 'Update Tunnel')

    def disable_tunnel(self, sender, app_data, user_data):
        tunnel = self.tunnels.get(user_data)
        if tunnel:
            tunnel['enabled'] = False
            if 'process' in tunnel:
                tunnel['process'].terminate()
                tunnel['process'].wait()
                del tunnel['process']
        self.update_tunnel_list()

    def update_tunnel_list(self):
        dpg.delete_item('tunnel_list', children_only=True)

        with dpg.table(header_row=True, parent='tunnel_list'):
            dpg.add_table_column(label="Name")
            dpg.add_table_column(label="Host")
            dpg.add_table_column(label="Remote Host Username")
            dpg.add_table_column(label="Local Port")
            dpg.add_table_column(label="Remote Port")
            dpg.add_table_column(label="Jump Host")
            dpg.add_table_column(label="Jump Host Username")
            dpg.add_table_column(label="Enabled")
            dpg.add_table_column(label="OnOff", width_fixed=True, init_width_or_weight=43)
            dpg.add_table_column(label="Edit", width_fixed=True, init_width_or_weight=43)
            dpg.add_table_column(label="Delete", width_fixed=True, init_width_or_weight=49)

            for tunnel in self.tunnels.values():
                with dpg.table_row():
                    dpg.add_text(tunnel['name'])
                    dpg.add_text(tunnel['host'])
                    dpg.add_text(tunnel['remote_username'])
                    dpg.add_text(tunnel['local_port'])
                    dpg.add_text(tunnel['remote_port'])
                    dpg.add_text(tunnel['jump_host'])
                    dpg.add_text(tunnel['jump_username'])
                    dpg.add_text(str(tunnel.get('enabled', False)))
                    if tunnel.get('enabled', False):
                        dpg.add_button(label="Disable", callback=self.disable_tunnel, user_data=tunnel['name'])
                    else:
                        dpg.add_button(label="Enable", callback=self.enable_tunnel, user_data=tunnel['name'])
                    dpg.add_button(label="Select", callback=self.select_tunnel, user_data=tunnel['name'])
                    dpg.add_button(label="Delete", callback=self.delete_tunnel, user_data=tunnel['name'])

    def name_input_callback(self, sender, app_data, user_data):
        print("name_input_callback triggered")
        tunnel_name = dpg.get_value('name_input')
        if tunnel_name in self.tunnels:
            dpg.set_item_label('add_button', 'Update Tunnel')
        else:
            dpg.set_item_label('add_button', 'Add Tunnel')

    def resize_callback(self, sender, app_data):
        width, height = dpg.get_viewport_client_width(), dpg.get_viewport_client_height()
        dpg.set_item_width('main_window', width)
        dpg.set_item_height('main_window', height)

    def check_ssh_command(self):
        if subprocess.call("ssh -V", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) != 0:
            dpg.show_item('error_popup')
            return False
        return True

    def cleanup(self):
        for tunnel in self.tunnels.values():
            if 'process' in tunnel and tunnel['process'].poll() is None:
                tunnel['process'].terminate()
                tunnel['process'].wait()

    def __init__(self):
        dpg.create_context()
        dpg.create_viewport(title='SSH Tunnel Manager', width=1280, height=800)

        with dpg.window(label="SSH Tunnel Manager", tag='main_window', no_resize=True, no_collapse=True, no_close=True,
                        autosize=True):
            dpg.add_input_text(label="Name", tag='name_input', callback=self.name_input_callback)
            dpg.add_input_text(label="Host", tag='host_input')
            dpg.add_input_text(label="Remote Host Username", tag='remote_username_input')
            dpg.add_input_text(label="Local Port", tag='local_port_input')
            dpg.add_input_text(label="Remote Port", tag='remote_port_input')
            dpg.add_input_text(label="Jump Host", tag='jump_host_input')
            dpg.add_input_text(label="Jump Host Username", tag='jump_username_input')
            dpg.add_input_text(label="SSH Key Path", tag='ssh_key_input')
            dpg.add_button(label="Add Tunnel", callback=self.add_tunnel, tag='add_button')
            dpg.add_separator()
            dpg.add_text("Tunnels:")
            with dpg.child_window(tag='tunnel_list', autosize_x=True, autosize_y=True):
                pass

        with dpg.window(label="Error", modal=True, show=False, tag='error_popup'):
            dpg.add_text("SSH command not found. Please download and install Git for Windows.")
            dpg.add_button(label="OK", callback=lambda: dpg.hide_item('error_popup'))

        self.check_ssh_command()
        self.load_tunnels()
        self.update_tunnel_list()

        dpg.set_viewport_resize_callback(self.resize_callback)
        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.start_dearpygui()
        dpg.destroy_context()

        atexit.register(self.cleanup)

    def __del__(self):
        self.cleanup()


if __name__ == "__main__":
    TunnelingToolApplication()

# pyinstaller TunnelingTool.spec
