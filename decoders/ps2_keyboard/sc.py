#A list of scancodes for the PS2 keyboard
ext = { 
    0x1F:'L Sup',
    0x14:'R Ctrl',
    0x27:'R Sup',
    0x11:'R Alt',
    0x2F:'Menu',
    0x12:'PrtScr',
    0x7C:'SysRq',
    0x70:'Insert',
    0x6C:'Home',
    0x7D:'Pg Up',
    0x71:'Delete',
    0x69:'End',
    0x7A:'Pg Dn',
    0x75:['Up arrow','^'],
    0x6B:['Left arrow','Left','<-'],
    0x74:['Right arrow','Right','->'],
    0x72:['Down arrow','Down','v'],
    0x4A:['KP /','/'],
    0x5A:['KP Ent','\n'], 
}

std = { 
    0x1C:'A',
    0x32:'B',
    0x21:'C',
    0x23:'D',
    0x24:'E',
    0x2B:'F',
    0x34:'G',
    0x33:'H',
    0x43:'I',
    0x3B:'J',
    0x42:'K',
    0x4B:'L',
    0x3A:'M',
    0x31:'N',
    0x44:'O',
    0x4D:'P',
    0x15:'Q',
    0x2D:'R',
    0x1B:'S',
    0x2C:'T',
    0x3C:'U',
    0x2A:'V',
    0x1D:'W',
    0x22:'X',
    0x35:'Y',
    0x1A:'Z',
    0x45:'0)',
    0x16:'1!',
    0x1E:'2@',
    0x26:'3#',
    0x25:'4$',
    0x2E:'5%',
    0x36:'6^',
    0x3D:'7&',
    0x3E:'8*',
    0x46:'9(',
    0x0E:'`~',
    0x4E:'-_',
    0x55:'=+',
    0x5D:'\|',
    0x66:'Backsp',
    0x29:['Space',' '],
    0x0D:['Tab','\t'],
    0x58:'CapsLk',
    0x12:'L Shft',
    0x14:'L Ctrl',
    0x11:'L Alt',
    0x59:'R Shft',
    0x5A:['Enter','\n'],
    0x76:'Esc',
    0x5:'F1',
    0x6:'F2',
    0x4:'F3',
    0x0C:'F4',
    0x3:'F5',
    0x0B:'F6',
    0x83:'F7',
    0x0A:'F8',
    0x1:'F9',
    0x9:'F10',
    0x78:'F11',
    0x7:'F12',
    0x7E:'ScrLck',
}


def key_decode(code, extended):
    try:
        c = ext[code] if extended else std[code]
    except KeyError:
        fs = '[E0%0X]' if extended else '[%0X]'
        c = fs % code
    if not isinstance(0,list):
        c = [c]
    return c