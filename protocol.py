from struct import pack, unpack

# import serial
from time import sleep

import sys
import threading
import _thread as thread


mst_consts = {
    "Unit_SF": 819200,  # pg 34 of protocal PDF (as of Issue 23)
    "Velo_SF": 43974656,
    "Acc_SF": 9012
}

LST_consts = {
    "Unit_SF": 409600,  # (25600 if not)
    "Velo_SF": 21987328,  # (25600 if not)
    "Acc_SF": 4506  # (25600 if not)
}

# for timeout


def quit_function(fn_name):
    print('{0} took too long'.format(fn_name), file=sys.stderr)
    sys.stderr.flush()
    thread.interrupt_main()  # raises KeyboardInterrupt


def exit_after(s):
    '''
    use as decorator to exit process if
    function takes longer than s seconds
    '''
    def outer(fn):
        def inner(*args, **kwargs):
            timer = threading.Timer(s, quit_function, args=[fn.__name__])
            timer.start()
            try:
                result = fn(*args, **kwargs)
            finally:
                timer.cancel()
            return result
        return inner
    return outer


def get_device_info(Device, destination, source):
    # req_info
    Device.write(pack('<HBBBB', 0x0005,
                      0x00, 0x00,
                      destination, source))

    # get_info
    read = Device.read(90)

    if read == b'':
        raise RuntimeError(
            "Cannot read from device, probably invalid destination address")

    header, ser_num, model_num, Type, \
        Frm_v, _, HW_v, Mod_state, \
        nchs = unpack('<6sL8s2s4s60s2s2sH', read)

    print("Model is ", model_num[:-2].decode("utf-8"))
    print("Number of channels = ", nchs)


def enable_motor(Device, destination, source, inner_channel):
    # Enable Stage
    # MGMSG_HW_NO_FLASH_PROGRAMMING
    Device.write(pack('<HBBBB', 0x0018,
                      0x00, 0x00,
                      destination, source))

    # MGMSG_MOD_SET_CHANENABLESTATE
    Device.write(pack('<HBBBB', 0x0210,
                      inner_channel, 0x01,
                      destination, source))
    sleep(0.1)
    print('Stage Enabled')


def disable_motor(Device, destination, source, inner_channel):
    # Disable Stage
    # MGMSG_MOD_SET_CHANENABLESTATE
    Device.write(pack('<HBBBB', 0x0210,
                      inner_channel, 0x02,
                      destination, source))
    print('Stage Disabled')
    sleep(0.1)


def get_backlash_distant(Device, destination, source, inner_channel, consts):
    # some params
    # MGMSG_MOT_REQ_GENMOVEPARAMS
    Device.write(pack('<HBBBB', 0x043B,
                      inner_channel, 0x00,
                      destination, source))

    # MGMSG_MOT_GET_GENMOVEPARAMS
    read = Device.read(12)
    if read == b'':
        raise RuntimeError(
            "Cannot read from device, probably invalid destination address")

    header, chan_indent, backlash = unpack('<6s2sl', read)

    print('Backlash: %.4f mm' % (backlash/float(consts["Unit_SF"])))


def set_backlash_distant(Device, destination, source, Channel, distance,
                         consts):
    # distance in mm
    distance_unit = int(distance*consts["Unit_SF"])
    Device.write(pack('<HBBBBHl', 0x043A,
                      0x06, 0x00,
                      destination | 0x80, source,
                      Channel, distance_unit))
    sleep(0.1)


def get_power_params(Device, destination, source, inner_channel):
    # MGMSG_MOT_REQ_POWERPARAMS
    Device.write(pack('<HBBBB', 0x0427,
                      inner_channel, 0x00,
                      destination, source))

    # MGMSG_MOT_GET_POWERPARAMS
    read = Device.read(12)

    if read == b'':
        raise RuntimeError(
            "Cannot read from device, probably invalid destination address")

    header, _, rest_f, move_f = unpack('<6sHHH', read)
    print('Rest power = {} %'.format(rest_f))
    print('Move power = {} %'.format(move_f))

    print('Rest power (hex) = {} %'.format(hex(rest_f)))
    print('Move power (hex) = {} %'.format(hex(move_f)))


def get_home_params(Device, destination, source, inner_channel, consts):
    # MGMSG_MOT_REQ_HOMEPARAMS 0x0441
    Device.write(pack('<HBBBB', 0x0441,
                      inner_channel, 0x00,
                      destination, source))

    # MGMSG_MOT_GET_HOMEPARAMS 0x0442

    read = Device.read(20)

    if read == b'':
        raise RuntimeError(
            "Cannot read from device, probably invalid destination address")

    header, \
        chan_ident, \
        home_dir, \
        limit_switch, \
        Home_v, \
        Offset_d = unpack('<6sHHHLl', read)

    print("Direction of homing (1=forward, 2=reverse) = ", home_dir)
    print("Limit switch (1=hardware reverse, 4=hardware forward) = ",
          limit_switch)
    print("Homing velocity (mm/sec) = ", Home_v/consts["Velo_SF"])
    print("Offset distance (mm) = ", Offset_d/consts["Unit_SF"])


def get_velocity_params(Device, destination, source, inner_channel, consts):
    # MGMSG_MOT_REQ_VELPARAMS
    Device.write(pack('<HBBBB', 0x0414,
                      inner_channel, 0x00,
                      destination, source))

    # MGMSG_MOT_GET_VELPARAMS
    read = Device.read(20)

    if read == b'':
        raise RuntimeError(
            "Cannot read from device, probably invalid destination address")

    header, chan_ident, min_vel, \
        accel, max_vel = unpack('<6sHLLL', read)

    print('Min velocity: %.4f mm/sec' % (min_vel/float(consts["Velo_SF"])))
    print('Max velocity: %.4f mm/sec' % (max_vel/float(consts["Velo_SF"])))
    print('Acceleration: %.4f mm/sec/sec' % (min_vel/float(consts["Acc_SF"])))


def get_limit_switch_params(Device, destination, source, inner_channel,
                            consts):
    # MGMSG_MOT_REQ_LIMSWITCHPARAMS
    Device.write(pack('<HBBBB', 0x0424,
                      inner_channel, 0x00,
                      destination, source))

    # MGMSG_MOT_GET_LIMSWITCHPARAMS
    read = Device.read(22)

    if read == b'':
        raise RuntimeError(
            "Cannot read from device, probably invalid destination address")

    header, chan_ident, CW_hard, \
        CCW_hard, CW_soft, CCW_soft, \
        limit_switch = unpack('<6sHHHLLH', read)

    print('1 = ignore/not present, 2 = make switch on contact')
    print('CW hard limit switch = {}'.format(CW_hard))
    print('CCW hard limit switch = {}'.format(CCW_hard))
    print('CW soft limit = {}'.format(CW_soft/consts["Unit_SF"]))
    print('CCW soft limit = {}'.format(CCW_soft/consts["Unit_SF"]))
    print('Soft limit switch = {}'.format(limit_switch))


def get_current_position(Device, destination, source, inner_channel, consts):
    # Request Position; MGMSG_MOT_REQ_POSCOUNTER
    #clean serial data
    out = 'output bytes'
    while out != b'':
        out = Device.read(50)

    Device.write(pack('<HBBBB', 0x0411,
                      inner_channel, 0x00,
                      destination, source))

    # Read back position returned the BSC;MGMSG_MOT_GET_POSCOUNTER
    read = Device.read(12)

    if read == b'':
        raise RuntimeError(
            "Cannot read from device, probably invalid destination address")

    header, chan_ident, position_dUnits = unpack('<6sHl', read)
    getpos = position_dUnits/float(consts["Unit_SF"])
    print('Position: %.4f mm' % (getpos))
    return getpos


def set_current_position(Device, destination, source, inner_channel, position, consts):
    #not finished
    #MGMSG_MOT_SET_POSCOUNTER
    setpos = position * float(consts["Unit_SF"])
    Device.write(pack('<HBBBB', 0x0411,
                      destination, source,
                      inner_channel, setpos))

    sleep(0.1)


def set_power_params(Device, destination, source, Channel, rest, move):
    # rest and move in %
    Device.write(pack('<HBBBBHHH', 0x0426,
                      0x06, 0x00,
                      destination | 0x80, source,
                      Channel, rest, move))
    sleep(0.1)


def set_home_params(Device, destination, source, Channel, homing_vel,
                    offset_dist, consts):
    # MGMSG_MOT_SET_HOMEPARAMS
    hom_vel_unit = int(homing_vel*consts["Velo_SF"])
    off_dist_unit = int(offset_dist*consts["Unit_SF"])
    Device.write(pack('<HBBBBHHHLL', 0x0440,
                      0x0E, 0x00,
                      destination | 0x80, source,
                      Channel, 0x0002, 0x0001, hom_vel_unit, off_dist_unit))
    sleep(0.1)


def set_velocity_params(Device, destination, source, Channel, min_vel, max_vel,
                        accel, consts):
    # MGMSG_MOT_SET_VELPARAMS
    min_vel_unit = int(min_vel*consts["Velo_SF"])
    max_vel_unit = int(max_vel*consts["Velo_SF"])
    accel_unit = int(accel*consts["Acc_SF"])

    print(min_vel_unit, max_vel_unit, accel_unit)

    Device.write(pack('<HBBBBHLLL', 0x0413,
                      0x0E, 0x00,
                      destination | 0x80, source,
                      Channel, min_vel_unit, accel_unit, max_vel_unit))
    sleep(0.1)


def set_limit_switch_params(Device, destination, source, Channel, CW_hard,
                            CWC_hard, CW_soft, CCW_soft, consts):
    # CW_soft and CCW_soft in mm
    CW_soft_Unit = int(consts["Unit_SF"]*CW_soft)
    CCW_soft_Unit = int(consts["Unit_SF"]*CCW_soft)
    Device.write(pack('<HBBBBHHHLLH', 0x0423,
                      0x10, 0x00,
                      destination | 0x80, source, Channel, CW_hard, CWC_hard,
                      CW_soft_Unit, CCW_soft_Unit, 0x0002))
    sleep(0.1)


def homed(Device):
    tmp = 0
    while tmp != 0x0444:
        a = Device.read(2)
        if a != b'':
            res = unpack('<H', a)
            tmp = res[0]


def completed(Device):
    tmp = 0
    while tmp != 0x0464:
        a = Device.read(2)
        if a != b'':
            res = unpack('<H', a)
            tmp = res[0]


@exit_after(120)
def move_home(Device, destination, source, inner_channel):
    # Home Stage; MGMSG_MOT_MOVE_HOME
    Device.write(pack('<HBBBB', 0x0443,
                      inner_channel, 0x00,
                      destination, source))
    print('Homing stage...')

    homed(Device)
    print('Move complete')


def move_absolute(Device, destination, source, inner_channel, position,
                  consts):
    # MGMSG_MOT_MOVE_ABSOLUTE
    # position in mm
    dUnitpos = int(consts["Unit_SF"]*position)
    Device.write(pack('<HBBBBHl', 0x0453,
                      0x06, 0x00,
                      destination | 0x80, source,
                      inner_channel, dUnitpos))
    print('Moving stage')

    # dangerous! may be smthng to move independently and wait everyone
    # for completion?


def move_relative(Device, destination, source, inner_channel, distance,
                  consts):
    # MGMSG_MOT_MOVE_RELATIVE
    # distance in mm
    dUnitpos = int(consts["Unit_SF"]*distance)
    Device.write(pack('<HBBBBHl', 0x0448,
                      0x06, 0x00,
                      destination | 0x80, source,
                      inner_channel, dUnitpos))
    print('Moving stage')

    tmp = 0
    while tmp != 0x0464:
        a = Device.read(2)
        if a != b'':
            res = unpack('<H', a)
            tmp = res[0]

    # dangerous! may be smthng to move independently and wait everyone
    # for completion?


# NANOTRACK

def get_nt_mode(Device, destination, source):
    # MGMSG_PZ_REQ_NTMODE
    """
    state:
    0x01 = Piezo
    0x02 = Latch
    0x03 = Track, signal low
    0x04 = Track, signal OK
    mode:
    0x01 = dual axes
    0x02 = horizontal
    0x03 = vertical
    """

    Device.write(pack('<HBBBB', 0x0604,
                      0x00, 0x00,
                      destination, source))

    read = Device.read(6)

    if read == b'':
        raise RuntimeError(
            "Cannot read from device, probably invalid destination address")

    _, state, mode, _, _ = unpack('<HBBBB', read)

    print('See protocol for description')
    print('Nanotrack state = {}'.format(state))
    print('Nanotrack mode = {}'.format(mode))

def get_diode_value(Device, destination, source):
    # MGMSG_PZ_REQ_NTTIAREADING
    #clean seril data

    out = 'output bytes'
    while out != b'':
        out = Device.read(50)

    Device.write(pack('<HBBBB', 0x0639,
                      0x00, 0x00,
                      destination, source))

    read = Device.read(16)

    if read == b'':
        raise RuntimeError(
            "Cannot read from device, probably invalid destination address")

    _, _, _, _, _, AbsReading, RelReading, Range, UnderOverRead = unpack('<HBBBBfHHH', read)

    print('Absolute diode value = {}'.format(AbsReading))
    print('Relative diode value = {} percents'.format(RelReading/32767))
    print('Range = {}'.format(Range))
    print('UnderOverRead = {}'.format(UnderOverRead))

    return [AbsReading, RelReading, Range, UnderOverRead]

def set_nt_mode(Device, destination, source, State):
    # MGMSG_PZ_SET_NTMODE
    """
    State:
    0x01 = Piezo
    0x02 = Latch
    0x03 = Track (horizontal+vertical)
    0x04 = Track (horizontal)
    0x05 = Track (vertical)
    """

    Device.write(pack('<HBBBB', 0x0603,
                      State, 0x00,
                      destination, source))

def set_circ_hom_pos(Device, destination, source):
    #MGMSG_PZ_SET_NTCIRCHOMEPOS
    CircHomePosA = 32000 #0 to 65535
    CircHomePosB = 32000
    Device.write(pack('<HBBBBHH', 0x0609, 0x04, 0x00,
                      destination | 0x80, source,
                      CircHomePosA, CircHomePosB))


# trouble here, no response after request
def get_circ_hom_pos2(Device, destination, source):
    # MGMSG_PZ_GET_NTCIRCHOMEPOS
    Device.read(40)
    # Request:
    Device.write(pack('<HBBBB', 0x0610,
                      0x00, 0x00,
                      destination, source))
    x = pack('<HBBBB', 0x0610,
                      0x00, 0x00,
                      0x25, source)
    print(x)
    print(unpack('<HBBBB', x))
    # Get:
    read = Device.read(10)
    print(read)
    
    if read == b'':
        raise RuntimeError(
            "Cannot read from device, probably invalid destination address")

   # header, CircPosA, CircPosB = unpack('<HBBBBHH', read)
    header, CircPosA, CircPosB = unpack('<HHH',read)
    # 65535 -> normalization to print %
    print('See protocol for description')
    print(read)
    print('Coordinate A of circle = {}'.format(CircPosA))
    print('Coordinate B of circle = {}'.format(CircPosB))



def move_nanotrack_home(Device, destination, source):
    #MGMSG_PZ_MOVE_NTCIRCTOHOMEPOS
    Device.write(pack('<HBBBB', 0x0612,
                      0x00, 0x00,
                      destination, source))

def get_scan_circle_params(Device, destination, source):
    # MGMSG_PZ_GET_NTCIRCPARAMS
    # Request:
    Device.write(pack('<HBBBB', 0x0619,
                      0x01, 0x00,
                      destination, source))
    # Get:
    read = Device.read(18)

    if read == b'':
        raise RuntimeError(
            "Cannot read from device, probably invalid destination address")

    header, CircDiaMode, CircDiaSW, CircOscFreq, \
        AbsPwrMinCircDia, AbsPwrMaxCircDia, \
        AbsPwrAdjustType = unpack('<6sHHHHHH', read)

    print('See protocol for descriprion')
    print('Circle diameter adjustment mode = {}'.format(CircDiaMode))
    print('Circle diameter = {} '
          '(makes sense only if mode = 0x01)'.format(CircDiaSW))
    print('Circle frequency = {} Hz'.format(
        7000/CircOscFreq))  # 7000/CircOscFreq
    print('Minimum circle diameter = {} '
          '(if mode = 0x02)'.format(AbsPwrMinCircDia))
    print('Maximum circle diameter = {} '
          '(if mode = 0x02)'.format(AbsPwrMaxCircDia))
    print('Adjustment type of circle position = {} '
          '(if mode = 0x02)'.format(AbsPwrAdjustType))


def set_scan_circle_params(Device, destination, source, CircDiaMode=2, CircDiaSW=50000, CircOscFreq=0x0078, AbsPwrAdjustType = 1, AbsPwrMinCircDia = 2000, AbsPwrMaxCircDia = 32000):
    # Force parameters
    #CircOscFreq = 0x0078 #120
    #AbsPwrMinCircDia = 2000  # 32767 = 50% = max
    #AbsPwrMaxCircDia = 32000
    

    Device.write(pack('<HBBBBHHHHHH', 0x0618, 0x0c, 0x00,
                      destination | 0x80, source,
                      CircDiaMode, CircDiaSW, CircOscFreq,
                      AbsPwrMinCircDia, AbsPwrMaxCircDia,
                      AbsPwrAdjustType))


def get_feedback_mode(Device, destination, source):
    # MGMSG_PZ_GET_NTFEEDBACKSRC
    # Request:
    Device.write(pack('<HBBBB', 0x063c,
                      0x00, 0x00,
                      destination, source))
    # Get:
    read = Device.read(6)

    if read == b'':
        raise RuntimeError(
            "Cannot read from device, probably invalid destination address")
    _, mode, _, _, _ = unpack('<HBBBB', read)

    print('Feedback mode = {}'.format(mode))


def set_feedback_mode(Device, destination, source, mode):
    # MGMSG_PZ_SET_NTFEEDBACKSRC
    """
    Mode:
    0x01 = TIA input (optical fiber in)
    0x02 = EXT (1V range) - external power meter, voltage feedback
    0x03 = EXT (2V range)
    0x04 = EXT (5V range)
    0x05 = EXT (10V range)
    """
    Device.write(pack('<HBBBB', 0x063b,
                      mode, 0x00,
                      destination, source))
              
def curent_circ_pos(Device, destination, source):
    #MGMSG_PZ_REQ_NTCIRCCENTREPOS
    
    Device.write(pack('<HBBBB', 0x0613,
                      0x01, 0x00,
                      destination, source))
                      
    # Get:
    read = Device.read(20)

    if read == b'':
        raise RuntimeError(
            "Cannot read from device, probably invalid destination address")
            
    _, _, _, _, _, posA, posB, AbsReading, RelReading, Range, UnderOverRead = unpack('<HBBBBHHlHHH', read)

    return(posA, posB, AbsReading, RelReading, Range, UnderOverRead)
    
    
def get_table_of_diametre(Device, destination, source):
    #MGMSG_PZ_GET_NTCIRCDIALUT
    Device.write(pack('<HBBBB', 0x0622,
                      0x00, 0x00,
                      destination, source))
                      
    # Get:
    read = Device.read(38)

    if read == b'':
        raise RuntimeError(
            "Cannot read from device, probably invalid destination address")
            
    _, _, _, _, _, _, _, LUTVal1, LUTVal2, LUTVal3, LUTVal4, LUTVal5, LUTVal6, LUTVal7, LUTVal8, LUTVal9, LUTVal10, LUTVal11, LUTVal12, LUTVal13, LUTVal14 = unpack('<HBBBBHHHHHHHHHHHHHHHH', read)

    return(LUTVal1, LUTVal2, LUTVal3, LUTVal4, LUTVal5, LUTVal6, LUTVal7, LUTVal8, LUTVal9, LUTVal10, LUTVal11, LUTVal12, LUTVal13, LUTVal14)


def set_table_of_diametre(Device, destination, source, list_of_diameters):
    #MGMSG_PZ_SET_NTCIRCDIALUT
    Device.write(pack('<HBBBBHHHHHHHHHHHHHHHH', 0x0621,
                      0x20, 0x00,
                      destination, source, *list_of_diameters))
                      
   
