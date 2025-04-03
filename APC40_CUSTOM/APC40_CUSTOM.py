# Decompiled with PyLingual (https://pylingual.io)
# Internal filename: output/Live/mac_universal_64_static/Release/python-bundle/MIDI Remote Scripts/APC40/APC40.py
# Bytecode version: 3.11a7e (3495)
# Source timestamp: 2025-02-07 10:25:55 UTC (1738923955)

import re
from functools import partial
import signal, sys
import math
from collections import defaultdict

from _Framework.Task import TimerTask
from _Framework.ButtonMatrixElement import ButtonMatrixElement
from _Framework.ChannelTranslationSelector import ChannelTranslationSelector
from _Framework.ComboElement import ComboElement
from _Framework.ControlSurface import OptimizedControlSurface
from _Framework.Layer import Layer, SimpleLayerOwner
from _Framework.ModesComponent import ModesComponent
from _Framework.Resource import PrioritizedResource
from _Framework.SessionZoomingComponent import SessionZoomingComponent
from _Framework.Util import nop, recursive_map
from _APC.APC import APC
from _APC.ControlElementUtils import make_button, make_encoder, make_pedal_button, make_ring_encoder, make_slider
from _APC.DetailViewCntrlComponent import DetailViewCntrlComponent
from _APC.DeviceBankButtonElement import DeviceBankButtonElement
from _APC.DeviceComponent import DeviceComponent
from _APC.MixerComponent import MixerComponent
from _APC.SkinDefault import make_biled_skin, make_default_skin
from .SessionComponent import SessionComponent
from .TransportComponent import TransportComponent

from _Framework.InputControlElement import MIDI_NOTE_TYPE
from _Framework.ButtonElement import ButtonElement

# SESSION_WIDTH = 8
SESSION_WIDTH = 4
SESSION_HEIGHT = 5
# MIXER_SIZE = 8
MIXER_SIZE = 4
FALLBACK_CONTROL_OWNER_PRIORITY = (-1)
TAG='[MY_APC40]'

logger = None
regex_pattern = re.compile(r'\[[^\]]*?(\d+(?![A-Za-z]))')

def log(msg):
    global logger
    if logger is not None:
        logger(msg)        

def make_on_off_button(channel, identifier, *a, **k):
    return ButtonElement(False, MIDI_NOTE_TYPE, channel, identifier, *a, **k)

class APC40_CUSTOM(APC):
    def __init__(self, *a, **k):
        super(APC40_CUSTOM, self).__init__(*a, **k)
        self._color_skin = make_biled_skin()
        self._default_skin = make_default_skin()
        with self.component_guard():
            global logger
            logger = self.log_message
            log('\n\n HELLO MUSIC WORLD \n')

            self._create_controls()
            self._create_session()
            self._create_mixer()
            self._create_device()
            self._create_detail_view_control()
            self._create_transport()
            # self._create_global_control()
            self._create_fallback_control_owner()
            self._session.set_mixer(self._mixer)
            self.set_highlighting_session_component(self._session)
            self.set_device_component(self._device)
            for component in self.components:
                component.set_enabled(False)

            self._beat = 0
            self._metronome_led_buttons = []
            self._performance_pads = []
            self._clip_slot_listeners = {}
            self._clip_listeners = {}
            self.create_performance_pads()
            self.create_metronome_led_buttons()
            self.song().add_current_song_time_listener(self.song_time_listener)
            self.song().add_is_playing_listener(self.song_is_playing_listener)
            self.init_deck_load_buttons()
            self.init_deck_clear_buttons()
            self.init_bpm_buttons()
            self.init_set_warp_mode_complex_buttons()
            self.init_set_bpm_from_clip_buttons()
            self.init_clip_navigation_buttons()
            self.init_clip_slots_listeners()
            # self.init_loop_buttons()

            for i, btn in enumerate(self._select_buttons):
                btn.add_value_listener(lambda value, track_index=i: self.track_select_listener(track_index) if value == 127 else None)

            # Init performance pads color with some delay
            def __handler(*args):
                self.init_performance_pads_colors()

            timer_task = TimerTask(duration=5.0)
            timer_task.on_finish = __handler        
            self._tasks.add(timer_task)                

    def _with_shift(self, button):
        return ComboElement(button, modifiers=[self._shift_button])

    def _create_controls(self):
        log(f'{TAG} INITIALIZING CONTROLS...')
        make_color_button = partial(make_button, skin=self._color_skin)
        # self = partial(make_button, skin=self._color_skin)
        self._shift_button = make_button(0, 98, resource_type=PrioritizedResource, name='Shift_Button')
        self._right_button = make_button(0, 96, name='Bank_Select_Right_Button')
        self._left_button = make_button(0, 97, name='Bank_Select_Left_Button')
        self._up_button = make_button(0, 94, name='Bank_Select_Up_Button')
        self._down_button = make_button(0, 95, name='Bank_Select_Down_Button')
        self._session_matrix = ButtonMatrixElement(name='Button_Matrix')
        self._scene_launch_buttons_raw = [make_color_button(0, index + 82, name=f'Scene_%d_Launch_Button{index}') for index in range(SESSION_HEIGHT)]
        self._track_stop_buttons = [make_color_button(index, 52, name='Track_%d_Stop_Button' % index) for index in range(SESSION_WIDTH)]

        # Used for metronome beat led, instead of stop buttons ^_^
        self._my_metronome_buttons = [make_color_button(index, 52, name=f'Track_{index}_Beat_Button') for index in range(4, 8)]

        self._stop_all_button = make_button(0, 81, name='Stop_All_Clips_Button')
        # self._matrix_rows_raw = [make_color_button(track_index, scene_index + 53, name='%d_Clip_%d_Button' % (track_index, scene_index)) for track_index in range(SESSION_HEIGHT)]

        self._matrix_rows_raw = [
            [
                make_color_button(
                    track_index,
                    scene_index + 53,
                    name=f'{scene_index}_Clip_{track_index}_Button',
                )
                for track_index in range(SESSION_WIDTH)
            ]
            for scene_index in range(SESSION_HEIGHT)
        ]

        for row in self._matrix_rows_raw:
            self._session_matrix.add_row(row)
        self._selected_slot_launch_button = make_pedal_button(67, name='Selected_Slot_Launch_Button')
        self._selected_scene_launch_button = make_pedal_button(64, name='Selected_Scene_Launch_Button')
        self._volume_controls = []
        # self._arm_buttons = []
        self._solo_buttons = []
        self._mute_buttons = []
        self._select_buttons = []
        for index in range(MIXER_SIZE):
            self._volume_controls.append(make_slider(index, 7, name=f'{index}_Volume_Control'))
            # self._arm_buttons.append(make_color_button(index, 48, name=f'{index}_Arm_Button'))
            self._solo_buttons.append(make_color_button(index, 49, name=f'{index}_Solo_Button'))
            self._mute_buttons.append(make_color_button(index, 50, name=f'{index}_Mute_Button'))
            self._select_buttons.append(make_color_button(index, 51, name=f'{index}_Select_Button'))
        self._crossfader_control = make_slider(0, 15, name='Crossfader')
        self._master_volume_control = make_slider(0, 14, name='Master_Volume_Control')
        self._master_select_button = make_color_button(0, 80, name='Master_Select_Button')
        self._prehear_control = make_encoder(0, 47, name='Prehear_Volume_Control')
        self._device_bank_buttons = []
        self._device_param_controls_raw = []

        bank_button_labels = ('Clip_Track_Button', 'Device_On_Off_Button', 'Previous_Device_Button', 'Next_Device_Button', 'Detail_View_Button', 'Rec_Quantization_Button', 'Midi_Overdub_Button', 'Metronome_Button')

        for index in range(8):
            # self._device_bank_buttons.append(make_color_button(0, 58, 0, name=bank_button_labels[index]))
            self._device_bank_buttons.append(make_button(0, 58 + index, name=bank_button_labels[index]))
            # encoder_name = 'Device_Control_%d' % index
            # # ringed_encoder = make_ring_encoder(16 * index, 24 * index, name=encoder_name)
            # ringed_encoder = make_ring_encoder(16 + index, 24 + index, name=encoder_name)
            # self._device_param_controls_raw.append(ringed_encoder)

        self._play_button = make_button(0, 91, name='Play_Button')
        self._stop_button = make_button(0, 92, name='Stop_Button')
        self._record_button = make_button(0, 93, name='Record_Button')
        # self._nudge_up_button = make_button(0, 100, name='Nudge_Up_Button')
        # self._nudge_down_button = make_button(0, 101, name='Nudge_Down_Button')
        self._tap_tempo_button = make_button(0, 99, name='Tap_Tempo_Button')
        self._global_bank_buttons = []
        self._global_param_controls = []
        # for index in range(MIXER_SIZE):
        #     encoder_name = 'Track_Control_%d' % index
        #     # ringed_encoder = make_ring_encoder(48 * index, 56 * index, name=encoder_name)
        #     ringed_encoder = make_ring_encoder(48 + index, 56 + index, name=encoder_name)
        #     self._global_param_controls.append(ringed_encoder)
        self._global_bank_buttons = [make_on_off_button(0, 87 + index, name=name, skin=self._color_skin) for index, name in enumerate(('Pan_Button', 'Send_A_Button', 'Send_B_Button', 'Send_C_Button'))]        
        self._device_clip_toggle_button = self._device_bank_buttons[0]
        self._device_on_off_button = self._device_bank_buttons[1]
        self._detail_left_button = self._device_bank_buttons[2]
        self._detail_right_button = self._device_bank_buttons[3]
        self._detail_toggle_button = self._device_bank_buttons[4]
        self._rec_quantization_button = self._device_bank_buttons[5]
        self._overdub_button = self._device_bank_buttons[6]
        self._metronome_button = self._device_bank_buttons[7]

        def wrap_matrix(control_list, wrapper=nop):
            return ButtonMatrixElement(rows=[list(map(wrapper, control_list))])
        self._scene_launch_buttons = wrap_matrix(self._scene_launch_buttons_raw)
        self._track_stop_buttons = wrap_matrix(self._track_stop_buttons)
        self._volume_controls = wrap_matrix(self._volume_controls)
        # self._arm_buttons = wrap_matrix(self._arm_buttons)
        self._solo_buttons = wrap_matrix(self._solo_buttons)
        self._mute_buttons = wrap_matrix(self._mute_buttons)
        self._select_buttons = wrap_matrix(self._select_buttons)
        self._device_param_controls = wrap_matrix(self._device_param_controls_raw)
        # self._device_bank_buttons = wrap_matrix(self._device_bank_buttons, partial(DeviceBankButtonElement, modifiers=[self._shift_button]))
        self._device_bank_buttons = wrap_matrix(self._device_bank_buttons, partial(DeviceBankButtonElement, modifiers=[]))
        # self._shifted_matrix = ButtonMatrixElement(rows=recursive_map(self._with_shift, self._matrix_rows_raw))
        # self._shifted_scene_buttons = ButtonMatrixElement(rows=[[self._with_shift(button) for button in self._scene_launch_buttons_raw]])

        self._tap_tempo_button.add_value_listener(lambda value: self.on_tap_tempo_button() if value == 127 else None)
        self._rec_quantization_button.add_value_listener(lambda value: self.switch_view_listener() if value == 127 else None)
        log(f'{TAG} INITIALIZING CONTROLS DONE')

    def _create_session(self):        
        self._session = SessionComponent(SESSION_WIDTH, SESSION_HEIGHT, auto_name=True, enable_skinning=True, is_enabled=False, layer=Layer(track_bank_left_button=self._left_button, track_bank_right_button=self._right_button, scene_bank_up_button=self._up_button, scene_bank_down_button=self._down_button, stop_all_clips_button=self._stop_all_button, stop_track_clip_buttons=self._track_stop_buttons, scene_launch_buttons=self._scene_launch_buttons, clip_launch_buttons=self._session_matrix, slot_launch_button=self._selected_slot_launch_button, selected_scene_launch_button=self._selected_scene_launch_button))        
        # self._session_zoom = SessionZoomingComponent(self._session, name='Session_Overview', enable_skinning=True, is_enabled=False, layer=Layer(button_matrix=self._shifted_matrix, nav_up_button=self._with_shift(self._up_button), nav_down_button=self._with_shift(self._down_button), nav_left_button=self._with_shift(self._left_button), nav_right_button=self._with_shift(self._right_button), scene_bank_buttons=self._shifted_scene_buttons))
        log(f'{TAG} INITIALIZING SESSION DONE')

    def _create_mixer(self):
        # self._mixer = MixerComponent(MIXER_SIZE, auto_name=True, is_enabled=False, invert_mute_feedback=True, layer=Layer(volume_controls=self._volume_controls, arm_buttons=self._arm_buttons, solo_buttons=self._solo_buttons, mute_buttons=self._mute_buttons, track_select_buttons=self._select_buttons, shift_button=self._shift_button, crossfader_control=self._crossfader_control, prehear_volume_control=self._prehear_control))
        self._mixer = MixerComponent(MIXER_SIZE, auto_name=True, is_enabled=False, invert_mute_feedback=True, layer=Layer(volume_controls=self._volume_controls, solo_buttons=self._solo_buttons, mute_buttons=self._mute_buttons, track_select_buttons=self._select_buttons, shift_button=self._shift_button, crossfader_control=self._crossfader_control))
        self._mixer.master_strip().layer = Layer(volume_control=self._master_volume_control, select_button=self._master_select_button)

    def _create_device(self):
        self._device = DeviceComponent(name='Device_Component', is_enabled=False, layer=Layer(bank_buttons=self._device_bank_buttons, on_off_button=self._device_on_off_button), use_fake_banks=True, device_selection_follows_track_selection=True)
        ChannelTranslationSelector(8, name='Control_Translations')
        self._device.set_parameter_controls(tuple(self._device_param_controls_raw))

    def _create_detail_view_control(self):
        # self._detail_view_toggler = DetailViewCntrlComponent(name='Detail_View_Control', is_enabled=False, layer=Layer(device_clip_toggle_button=self._device_clip_toggle_button, detail_toggle_button=self._detail_toggle_button, device_nav_left_button=self._detail_left_button, device_nav_right_button=self._detail_right_button))
        self._detail_view_toggler = DetailViewCntrlComponent(name='Detail_View_Control', is_enabled=False, layer=Layer(device_clip_toggle_button=self._device_clip_toggle_button, detail_toggle_button=self._detail_toggle_button))

    def _create_transport(self):
        # self._transport = TransportComponent(name='Transport', is_enabled=False, layer=Layer(play_button=self._play_button, stop_button=self._stop_button, record_button=self._record_button, nudge_up_button=self._nudge_up_button, nudge_down_button=self._nudge_down_button, tap_tempo_button=self._tap_tempo_button, quant_toggle_button=self._rec_quantization_button, overdub_button=self._overdub_button, metronome_button=self._metronome_button))
        self._transport = TransportComponent(name='Transport', is_enabled=False, layer=Layer(play_button=self._play_button, stop_button=self._stop_button, metronome_button=self._metronome_button))
        self._bank_button_translator = ChannelTranslationSelector(name='Bank_Button_Translations', is_enabled=False)

    def _create_global_control(self):
        def set_pan_controls():
            for index, control in enumerate(self._global_param_controls):
                self._mixer.channel_strip(index).set_pan_control(control)
                self._mixer.channel_strip(index).set_send_controls((None, None, None))
                control.set_channel(0)

        def set_send_controls(send_index):
            for index, control in enumerate(self._global_param_controls):
                self._mixer.channel_strip(index).set_pan_control(None)
                # send_controls = (None, [], 3)
                # send_controls = [None, [], 3]
                send_controls = [None, None, None]
                send_controls[send_index] = control
                # self._mixer.channel_strip(index).set_send_controls(send_controls)
                self._mixer.channel_strip(index).set_send_controls(tuple(send_controls))
                control.set_channel(send_index + 1)
        encoder_modes = ModesComponent(name='Track_Control_Modes', is_enabled=False)
        encoder_modes.add_mode('pan', [set_pan_controls])
        encoder_modes.add_mode('send_a', [partial(set_send_controls, 0)])
        encoder_modes.add_mode('send_b', [partial(set_send_controls, 1)])
        encoder_modes.add_mode('send_c', [partial(set_send_controls, 2)])
        encoder_modes.selected_mode = 'pan'
        encoder_modes.layer = Layer(pan_button=self._global_bank_buttons[0], send_a_button=self._global_bank_buttons[1], send_b_button=self._global_bank_buttons[2], send_c_button=self._global_bank_buttons[3])
        self._translation_selector = ChannelTranslationSelector(name='Global_Translations')

    def _create_fallback_control_owner(self):
        self.register_disconnectable(SimpleLayerOwner(layer=Layer(_matrix=self._session_matrix, priority=FALLBACK_CONTROL_OWNER_PRIORITY)))

    def get_matrix_button(self, column, row):
        return self._matrix_rows_raw[row][column]

    def _product_model_id_byte(self):
        return 115

    # --------------------------------------------------------------------

    # Override to avoid double log
    def log_message(self, *message):        
        message = "(%s) %s" % (self.__class__.__name__, " ".join(map(str, message)))
        # Emette il messaggio solo attraverso _c_instance, evitando la chiamata a logger.info
        if self._c_instance:
            self._c_instance.log_message(message)

    def empty_listener(self, o):
        pass

    def create_metronome_led_buttons(self):
        for index in range(4, 8):            
            button = ButtonElement(
                is_momentary=False,
                msg_type=MIDI_NOTE_TYPE,
                channel=index, # midi channel
                identifier=52, # midi note
                name=f'Metronome_Led_Button_{index}',
                skin=self._color_skin)

            # Apparently if we don't add a listener, we can't change the color of the button...Another mystery
            button.add_value_listener(lambda value, btn=button: self.empty_listener(btn))
            self._metronome_led_buttons.append(button)

    def song_time_listener(self):
        prev_beat = self._beat

        # Documentation at https://nsuspray.github.io/Live_API_Doc/11.0.0.xml
        self._beat = self.song().get_current_beats_song_time().beats

        if prev_beat != self._beat:
            if self._beat == 1:
                self._metronome_led_buttons[3].set_light('Session.ClipEmpty')
                self._metronome_led_buttons[0].set_light('Session.ClipStarted')                            
            elif self._beat == 2:
                self._metronome_led_buttons[0].set_light('Session.ClipEmpty')
                self._metronome_led_buttons[1].set_light('Session.ClipStarted')                
            elif self._beat == 3:
                self._metronome_led_buttons[1].set_light('Session.ClipEmpty')
                self._metronome_led_buttons[2].set_light('Session.ClipStarted')
            elif self._beat == 4:
                self._metronome_led_buttons[2].set_light('Session.ClipEmpty')
                self._metronome_led_buttons[3].set_light('Session.ClipStarted')            

            for track in self.song().tracks[:SESSION_WIDTH]:
                if track.playing_slot_index > -1:
                    clip = track.clip_slots[track.playing_slot_index].clip
                    remaining_bars = int((min(clip.loop_end, clip.end_marker) // 4) - (clip.playing_position // 4))
                    beat_index_backward = 4 - (round(clip.playing_position) % 4)
                    t = f'{remaining_bars}.{beat_index_backward}¦'
                    tokens = clip.name.split('¦')
                    new_clip_name = t + '¦'.join(tokens[1:])
                    
                    # We can't update Ableton UI in a listener notification. We have to defer the task.
                    task = TimerTask(duration=0.01)  # delay molto breve                    
                    task.on_finish = lambda clip=clip, new_clip_name=new_clip_name: setattr(clip, 'name', new_clip_name)
                    self._tasks.add(task)


    def song_is_playing_listener(self):
        # Turn off metronome buttons on stop
        if not self.song().is_playing:
            for button in self._metronome_led_buttons:
                button.set_light('Session.ClipEmpty')
        # Just in case the pads colors have not been initialized, for whatever reason
        self.init_performance_pads_colors()

    def create_performance_pads(self):                
        for scene_index in range(SESSION_HEIGHT):
            row = []
            for track_index in range(4, 8):                
                button = ButtonElement(
                    is_momentary=True,
                    msg_type=MIDI_NOTE_TYPE,
                    channel=track_index, # midi channel
                    identifier=scene_index + 53, # midi note
                    name=f'Performance_Pad_{scene_index}_{track_index}',
                    skin=self._color_skin)
                                
                idle_color = 'Session.ClipRecording' # red color
                button.add_value_listener(lambda value, btn=button, idle_color=idle_color: self.on_pad_value(value, btn, idle_color))
                row.append(button)
            self._performance_pads.append(row)                      
    
    def on_pad_value(self, value, button, idle_color):        
        if value:
            button.set_light('Session.ClipStarted') # green when pushed
        else:
            button.set_light(idle_color) # reset to the idle color when released

    def init_performance_pads_colors(self):
        log(f'INITIALIZED PERFOMANCE PADS COLORS')
        if self._performance_pads:
            for scene_index in range(SESSION_HEIGHT):
                for track_index in range(4):
                    button = self._performance_pads[scene_index][track_index]
                    button.set_light('Session.ClipRecording')

    def init_deck_clear_buttons(self):
        self._deck_clear_buttons = []
        for index in range(4, 8):            
            btn = ButtonElement(
                is_momentary=True,
                msg_type=MIDI_NOTE_TYPE,
                channel=index, # midi channel
                identifier=48, # midi note
                name=f'{index}_Deck_Clear_Button',
                skin=self._color_skin)            
            self._deck_clear_buttons.append(btn)

        for i in range(4):
            self._deck_clear_buttons[i].add_value_listener(lambda value, track_index=i: self.on_deck_clear(track_index))


    def on_deck_clear(self, track_index):
        view = self.application().view
        view.focus_view('Session')

        # Check if we are tying to access a track that doesn't exist
        if len(self.song().tracks) - 1 < track_index:
            return

        track = self.song().tracks[track_index]

        # Delete clip listeners
        if track_index in self._clip_listeners:
            for clip, listener in self._clip_listeners[track_index].items():
                clip.remove_playing_status_listener(listener)                
            del self._clip_listeners[track_index]

        # Delete clip slot listeners
        if track_index in self._clip_slot_listeners:
            for clip_slot, listener in self._clip_slot_listeners[track_index].items():
                clip_slot.remove_is_triggered_listener(listener)                
            del self._clip_slot_listeners[track_index]

        # Delete all clips in the track
        for clip_slot in track.clip_slots:
            if clip_slot.has_clip:
                clip_slot.delete_clip()

        
        # Put focus on the first slot
        first_clip_slot = track.clip_slots[0]
        self.song().view.highlighted_clip_slot = first_clip_slot

        # If the track header is selected, the focus will be on the track and not on the clip slot so we have to use this trick.
        view.scroll_view(1, 'Session', False) # 1=scroll down
        view.scroll_view(0, 'Session', False) # 0=scroll up

    def init_deck_load_buttons(self):
        self._deck_load_buttons = []
        for index in range(4):            
            btn = ButtonElement(
                is_momentary=True,
                msg_type=MIDI_NOTE_TYPE,
                channel=index, # midi channel
                identifier=48, # midi note
                name=f'{index}_Deck_Load_Button',
                skin=self._color_skin)           
            self._deck_load_buttons.append(btn)

        for i in range(4):
            # NB: use self.on_deck_load(track_index, add_trigger_next_clip=True) to automatically trigger next clip without using follow actions (for dj loops)
            self._deck_load_buttons[i].add_value_listener(lambda value, track_index=i: self.on_deck_load(track_index, False) if value == 127 else None)

    def init_clip_slots_listeners(self, only_this_track_index=None, add_trigger_next_clip=False):        
        song = self.song()
        for track_index, track in enumerate(song.tracks[:SESSION_WIDTH]):
            if only_this_track_index is not None and track_index != only_this_track_index:
                continue            

            clip_slots_with_clip = [clip_slot for clip_slot in track.clip_slots if clip_slot.has_clip]
            last_clip_slot = clip_slots_with_clip[-1] if len(clip_slots_with_clip) > 0 else None

            for clip_slot_index, clip_slot in enumerate(track.clip_slots):
                clip = clip_slot.clip
                if not clip:
                    continue

                # Clear clip listeners    
                if track_index in self._clip_listeners:
                    if clip in self._clip_listeners[track_index]:
                        listener = self._clip_listeners[track_index][clip]
                        clip.remove_playing_status_listener(listener)
                        del self._clip_listeners[track_index][clip]        

                # Clear clip slot listeners
                if track_index in self._clip_slot_listeners:
                    if clip_slot in self._clip_slot_listeners[track_index]:
                        listener = self._clip_slot_listeners[track_index][clip_slot]
                        clip_slot.remove_is_triggered_listener(listener)
                        del self._clip_slot_listeners[track_index][clip_slot]

                # Add clip listener
                def clip_playing_status_listener(*args, clip=clip):
                    if not clip.is_playing:                        
                        tokens = clip.name.split('¦')                        
                        original_clip_name = '¦' + '¦'.join(tokens[-2:])                        
                        # We can't update Ableton UI in a listener notification. We have to defer the task.
                        task = TimerTask(duration=0.1)
                        task.on_finish = lambda clip=clip, original_clip_name=original_clip_name: setattr(clip, 'name', original_clip_name)
                        self._tasks.add(task)

                clip.add_playing_status_listener(clip_playing_status_listener)
                if not track_index in self._clip_listeners:
                    self._clip_listeners[track_index] = {}
                self._clip_listeners[track_index][clip] = clip_playing_status_listener

                # Add clip_slot listener
                def clip_slot_triggered_listener(*args, track=track, track_index=track_index, clip_slot=clip_slot, clip_slot_index=clip_slot_index):                    
                    clip = clip_slot.clip 
                    if clip and clip.is_playing and song.view.follow_song and song.view.selected_track == track:                                                
                        song.view.highlighted_clip_slot = clip_slot
                        self._session.set_offsets(0, clip_slot_index)
                        clip_slot.clip.view.show_loop()                                        

                clip_slot.add_is_triggered_listener(clip_slot_triggered_listener)
                if not track_index in self._clip_slot_listeners:
                    self._clip_slot_listeners[track_index] = {}
                self._clip_slot_listeners[track_index][clip_slot] = clip_slot_triggered_listener
                
                # Add clip length (bars) as prefix to the clip name, if not present
                if (clip.name[0] != '¦'):
                    clip.name = f'¦{math.floor(int(clip.length) / 4)}¦ {clip.name}'

                # Set start/end markers the same as loop markers (only for clips that doesn't have looping already activated)
                if not clip.looping:
                    # NB: we have to enable looping before making changes. Also note that when looping=False, loop_start is the start_marker
                    # and loop_end is the end_marker. Not sure why, but this the way.
                    clip.looping = True
                    clip.loop_start = clip.start_marker
                    clip.loop_end = clip.end_marker
                    # clip.looping = False

                # Set clip grid to 1 bar and zoom
                clip.view.grid_quantization = 4
                clip.view.show_loop()

                if add_trigger_next_clip:
                    # Custom playing next clip listener (to make DJ loops usable!)
                    # NB: for this to work with loops of 1/4, global quantization should be 1/4
                    def trigger_next_clip_listener(*args, clip=clip, clip_slot_index=clip_slot_index):
                        if clip.looping:
                            return
                        if clip.loop_end - clip.playing_position < 1:
                            next_clip_slot = track.clip_slots[clip_slot_index + 1]
                            if next_clip_slot.has_clip and not next_clip_slot.clip.is_triggered: 
                                next_clip_slot.clip.fire()
                                log(f'[{clip.name}] Triggered clip {next_clip_slot.clip.name}')                            

                    # Add listener (exclude last clip)
                    if clip != last_clip_slot.clip:
                        clip.add_playing_position_listener(trigger_next_clip_listener)

    def on_deck_load(self, track_index, add_trigger_next_clip=False):
        # log(f'LOADED DECK {track_index}')
        view = self.application().view
        view.focus_view('Session')
        song = self.song()

        # Check if we are tying to access a track that doesn't exist
        if len(song.tracks) - 1 < track_index:
            return

        track = song.tracks[track_index]        
        
        # Put focus on the first slot
        first_clip_slot = track.clip_slots[0]
        song.view.highlighted_clip_slot = first_clip_slot

        # If the track header is selected, the focus will be on the track and not on the clip slot so we have to use this trick.
        view.scroll_view(1, 'Session', False) # 1=scroll down
        view.scroll_view(0, 'Session', False) # 0=scroll up        
        
        # Wait clips to load from Bome before initializing listeners
        timer_task = TimerTask(duration=2.0)
        timer_task.on_finish = lambda: self.init_clip_slots_listeners(only_this_track_index=track_index, add_trigger_next_clip=add_trigger_next_clip)
        self._tasks.add(timer_task)

    def init_bpm_buttons(self):
        nudge_up_button = ButtonElement(
                is_momentary=True,
                msg_type=MIDI_NOTE_TYPE,
                channel=0, # midi channel
                identifier=100, # midi note
                name='Nudge_Up_Button')
        
        nudge_down_button = ButtonElement(
                is_momentary=True,
                msg_type=MIDI_NOTE_TYPE,
                channel=0, # midi channel
                identifier=101, # midi note
                name='Nudge_Down_Button')

        song = self.song()

        # Add bpm change listeners (only on note_on message)
        nudge_up_button.add_value_listener(lambda value: self.on_bmp_button(1) if value == 127 else None)
        nudge_down_button.add_value_listener(lambda value: self.on_bmp_button(-1) if value == 127 else None)

    def on_bmp_button(self, v):
        song = self.song()
        song.tempo += v

    def on_tap_tempo_button(self):
        song = self.song()        
        song.view.follow_song = not song.view.follow_song
        if song.view.follow_song:
            for track_index, track in enumerate(song.tracks[:SESSION_WIDTH]):
                if track.playing_slot_index > -1:                    
                    song.selected_track = track
                    song.view.highlighted_clip_slot = track.clip_slots[track.playing_slot_index]
                    self._session.set_offsets(0, track.playing_slot_index)                    
                    return
            
    def init_set_warp_mode_complex_buttons(self):
        btns = []
        for i in range(4, 8):
            b = ButtonElement(
                    is_momentary=True,
                    msg_type=MIDI_NOTE_TYPE,
                    channel=i,
                    identifier=49,
                    name=f'Warp_Complex_Button_{i}')
            btns.append(b)

        for i in range(4):
            btns[i].add_value_listener(lambda value, track_index=i: self.set_track_clips_warp_mode(track_index, 4) if value == 127 else None)

    def init_set_bpm_from_clip_buttons(self):
        btns = []
        for i in range(4, 8):
            b = ButtonElement(
                    is_momentary=True,
                    msg_type=MIDI_NOTE_TYPE,
                    channel=i,
                    identifier=50,
                    name=f'Bpm_Clip_Button_{i}')
            btns.append(b)

        for i in range(4):
            btns[i].add_value_listener(lambda value, track_index=i: self.set_bpm_from_playing_clip_name(track_index) if value == 127 else None)
        

    def set_bpm_from_playing_clip_name(self, track_index):
        track = self.song().tracks[track_index]

        for clip_slot in track.clip_slots:
            clip = clip_slot.clip
            if clip:
                # try extract bpm from clip name
                regex_result = regex_pattern.search(clip.name)                
                if regex_result:
                    target_bpm = int(regex_result.group(1))
                    log(f'Changed BPM to {target_bpm} from clip {clip.name}')
                    self.song().tempo = target_bpm                    
                    break  

        # Since we have matched song tempo, we can use repitch mode        
        self.set_track_clips_warp_mode(track_index, 3)


    def set_track_clips_warp_mode(self, track_index, warp_mode):
        # Possible warp_mode values:
        # 0 = beats
        # 1 = tones
        # 2 = texture
        # 3 = repitch
        # 4 = complex
        # 6 = complex_pro        

        track = self.song().tracks[track_index]
        for clip_slot in track.clip_slots:
            clip = clip_slot.clip
            if clip:                
                clip.warp_mode = warp_mode

    # Toggle between arranger and session view, basically what the tab key does
    def switch_view_listener(self):
        view = self.application().view        
        if view.focused_document_view == 'Session':
            view.focus_view('Arranger')
        else:
            view.focus_view('Session')

    def track_select_listener(self, track_index):
        song = self.song()
        track = song.tracks[track_index]

        if track.playing_slot_index > -1:
            song.view.highlighted_clip_slot = track.clip_slots[track.playing_slot_index]
            if song.view.follow_song:
                self._session.set_offsets(0, track.playing_slot_index)

    def move_highlighted_clip_start(self, bars_offset=1):
        view = self.song().view
        clip_slot = view.highlighted_clip_slot
        track = clip_slot.canonical_parent
        clip = clip_slot.clip

        if clip and clip.looping:
            start_marker_new = clip.start_marker + bars_offset * 4
            if start_marker_new >= clip.loop_start and start_marker_new < clip.loop_end:
                clip.start_marker = clip.start_marker + bars_offset * 4

    def reset_track_clips_start(self):
        for clip_slot in self.song().view.selected_track.clip_slots:
            clip = clip_slot.clip
            if clip and clip.looping:
                clip.start_marker = clip.loop_start

    def play_highlighted_clip(self):
        view = self.song().view
        clip_slot = view.highlighted_clip_slot
        if clip_slot.clip:
            clip_slot.fire()

    def init_clip_navigation_buttons(self):
        pan_btn, send_a_btn, send_b_btn, send_c_btn = self._global_bank_buttons

        pan_btn.add_value_listener(lambda value: self.move_highlighted_clip_start(-1) if value == 127 else None)
        send_a_btn.add_value_listener(lambda value: self.move_highlighted_clip_start(1) if value == 127 else None)
        send_b_btn.add_value_listener(lambda value: self.move_highlighted_clip_start(-4) if value == 127 else None)
        send_c_btn.add_value_listener(lambda value: self.move_highlighted_clip_start(4) if value == 127 else None)
        self._record_button.add_value_listener(lambda value: self.play_highlighted_clip() if value == 127 else None)
        self._overdub_button.add_value_listener(lambda value: self.reset_track_clips_start() if value == 127 else None)

    def init_loop_buttons(self):
        pan_btn, send_a_btn, send_b_btn, send_c_btn = self._global_bank_buttons
        
        def __toogle_loop(*args):
            for clip_slot in self.song().view.selected_track.clip_slots:
                if clip_slot.is_playing:
                    clip = clip_slot.clip
                    clip.looping = not clip.looping                        
                    return
        
        def __create_loop_4_bars(*args):
            for clip_slot in self.song().view.selected_track.clip_slots:
                if clip_slot.is_playing:
                    clip = clip_slot.clip
                    loop_start_new = round(clip.playing_position)
                    loop_end_new = loop_start_new + 16                        

                    # We have to handle various cases depending if looping is already activated
                    if not clip.looping:
                        if loop_end_new <= clip.loop_end:
                            clip.looping = True                                            
                            if loop_start_new > clip.loop_end:
                                clip.loop_end = loop_end_new
                                clip.loop_start = loop_start_new
                            else:
                                clip.loop_start = loop_start_new
                                clip.loop_end = loop_end_new
                    else:
                        if loop_end_new <= clip.end_marker:
                            if loop_start_new > clip.loop_end:
                                clip.loop_end = loop_end_new
                                clip.loop_start = loop_start_new
                            else:
                                clip.loop_start = loop_start_new
                                clip.loop_end = loop_end_new    

                    return
        
        def __halve_loop_length(*args):
            for clip_slot in self.song().view.selected_track.clip_slots:
                if clip_slot.is_playing and clip_slot.clip.looping:
                    clip = clip_slot.clip
                    loop_end_new = clip.loop_start + (clip.loop_end - clip.loop_start) / 2
                    # Avoid loops with length less then 1/4, since Ableton can go out of sync with shorter loops...
                    if loop_end_new - clip.loop_start >= 1:                                          
                        clip.loop_end = loop_end_new
                    return
        
        def __double_loop_length(*args):
            for clip_slot in self.song().view.selected_track.clip_slots:
                if clip_slot.is_playing and clip_slot.clip.looping:
                    clip = clip_slot.clip
                    loop_end_new = clip.loop_start + (clip.loop_end - clip.loop_start) * 2
                    
                    if loop_end_new < clip.end_marker:
                        clip.loop_end = loop_end_new
                    return            

        pan_btn.add_value_listener(lambda value: __toogle_loop() if value == 127 else None)
        send_a_btn.add_value_listener(lambda value: __create_loop_4_bars() if value == 127 else None)
        send_b_btn.add_value_listener(lambda value: __halve_loop_length() if value == 127 else None)
        send_c_btn.add_value_listener(lambda value: __double_loop_length() if value == 127 else None)
