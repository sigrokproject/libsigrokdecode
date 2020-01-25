/*---------------------------------------------------------------------------------------------------------------------------------------------------
 * irmpconfig.h
 *
 * DO NOT INCLUDE THIS FILE, WILL BE INCLUDED BY IRMP.H!
 *
 * Copyright (c) 2009-2019 Frank Meyer - frank(at)fli4l.de
 * Extensions for PIC 12F1820 W.Strobl 2014-07-20
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *---------------------------------------------------------------------------------------------------------------------------------------------------
 */

#ifndef _IRMP_H_
#  error please include only irmp.h, not irmpconfig.h
#endif

#ifdef IRMPCONFIG_STAGE1_H

/*---------------------------------------------------------------------------------------------------------------------------------------------------
 * Change IRMP_32_BIT here
 *
 * Normally, IRMP_32_BIT ist 0. Then we use irmp.command as a 16 bit value.
 * If you set IRMP_32_BIT to 1, we will use irmp.command as a 32 bit value.
 * A 32 bit command costs more CPU resources on 8 bit processors (e.g. AVR),
 * but there are IR protocols which need more than 16 bits for a reasonable
 * command value.
 *
 * If you want to use one of the following protocols, set IRMP_32_BIT to 1,
 * otherwise set it to 0:
 *    - MERLIN
 *---------------------------------------------------------------------------------------------------------------------------------------------------
 */

#define IRMP_32_BIT     1                                                                               // use 32 bit command value, 0 or 1

#endif // IRMPCONFIG_STAGE1_H
#ifdef IRMPCONFIG_STAGE2_H

/*---------------------------------------------------------------------------------------------------------------------------------------------------
 * Change F_INTERRUPTS if you change the number of interrupts per second,
 * Normally, F_INTERRUPTS should be in the range from 10000 to 15000, typical is 15000
 * A value above 15000 costs additional program space, absolute maximum value is 20000.
 * On PIC with XC8/C18 Compiler, use 15151 as the correct value.
 *---------------------------------------------------------------------------------------------------------------------------------------------------
 */
#ifndef F_INTERRUPTS
#  define F_INTERRUPTS                          20000   // interrupts per second, min: 10000, max: 20000, typ: 15000
#endif

/*---------------------------------------------------------------------------------------------------------------------------------------------------
 * Change settings from 1 to 0 if you want to disable one or more decoders.
 * This saves program space.
 *
 * 1 enable  decoder
 * 0 disable decoder
 *
 * The standard decoders are enabled per default.
 * Less common protocols are disabled here, you need to enable them manually.
 *
 * If you want to use FDC or RCCAR simultaneous with RC5 protocol, additional program space is required.
 * If you don't need RC5 when using FDC/RCCAR, you should disable RC5.
 * You cannot enable both DENON and RUWIDO, only enable one of them.
 *---------------------------------------------------------------------------------------------------------------------------------------------------
 */

// typical protocols, disable here!             Enable  Remarks                 F_INTERRUPTS            Program Space
#define IRMP_SUPPORT_SIRCS_PROTOCOL             1       // Sony SIRCS           >= 10000                 ~150 bytes
#define IRMP_SUPPORT_NEC_PROTOCOL               1       // NEC + APPLE + ONKYO  >= 10000                 ~300 bytes
#define IRMP_SUPPORT_SAMSUNG_PROTOCOL           1       // Samsung + Samsg32    >= 10000                 ~300 bytes
#define IRMP_SUPPORT_KASEIKYO_PROTOCOL          1       // Kaseikyo             >= 10000                 ~250 bytes

// more protocols, enable here!                 Enable  Remarks                 F_INTERRUPTS            Program Space
#define IRMP_SUPPORT_JVC_PROTOCOL               1       // JVC                  >= 10000                 ~150 bytes
#define IRMP_SUPPORT_NEC16_PROTOCOL             1       // NEC16                >= 10000                 ~100 bytes
#define IRMP_SUPPORT_NEC42_PROTOCOL             1       // NEC42                >= 10000                 ~300 bytes
#define IRMP_SUPPORT_MATSUSHITA_PROTOCOL        1       // Matsushita           >= 10000                  ~50 bytes
#define IRMP_SUPPORT_DENON_PROTOCOL             1       // DENON, Sharp         >= 10000                 ~250 bytes
#define IRMP_SUPPORT_RC5_PROTOCOL               1       // RC5                  >= 10000                 ~250 bytes
#define IRMP_SUPPORT_RC6_PROTOCOL               1       // RC6 & RC6A           >= 10000                 ~250 bytes
#define IRMP_SUPPORT_IR60_PROTOCOL              1       // IR60 (SDA2008)       >= 10000                 ~300 bytes
#define IRMP_SUPPORT_GRUNDIG_PROTOCOL           1       // Grundig              >= 10000                 ~300 bytes
#define IRMP_SUPPORT_SIEMENS_PROTOCOL           1       // Siemens Gigaset      >= 15000                 ~550 bytes
#define IRMP_SUPPORT_NOKIA_PROTOCOL             1       // Nokia                >= 10000                 ~300 bytes

// exotic protocols, enable here!               Enable  Remarks                 F_INTERRUPTS            Program Space
#define IRMP_SUPPORT_BOSE_PROTOCOL              1       // BOSE                 >= 10000                 ~150 bytes
#define IRMP_SUPPORT_KATHREIN_PROTOCOL          1       // Kathrein             >= 10000                 ~200 bytes
#define IRMP_SUPPORT_NUBERT_PROTOCOL            1       // NUBERT               >= 10000                  ~50 bytes
#define IRMP_SUPPORT_FAN_PROTOCOL               0       // FAN (ventilator)     >= 10000                  ~50 bytes
#define IRMP_SUPPORT_SPEAKER_PROTOCOL           1       // SPEAKER (~NUBERT)    >= 10000                  ~50 bytes
#define IRMP_SUPPORT_BANG_OLUFSEN_PROTOCOL      1       // Bang & Olufsen       >= 10000                 ~200 bytes
#define IRMP_SUPPORT_RECS80_PROTOCOL            1       // RECS80 (SAA3004)     >= 15000                  ~50 bytes
#define IRMP_SUPPORT_RECS80EXT_PROTOCOL         1       // RECS80EXT (SAA3008)  >= 15000                  ~50 bytes
#define IRMP_SUPPORT_THOMSON_PROTOCOL           1       // Thomson              >= 10000                 ~250 bytes
#define IRMP_SUPPORT_NIKON_PROTOCOL             1       // NIKON camera         >= 10000                 ~250 bytes
#define IRMP_SUPPORT_NETBOX_PROTOCOL            1       // Netbox keyboard      >= 10000                 ~400 bytes (PROTOTYPE!)
#define IRMP_SUPPORT_ORTEK_PROTOCOL             0       // ORTEK (Hama)         >= 10000                 ~150 bytes
#define IRMP_SUPPORT_TELEFUNKEN_PROTOCOL        1       // Telefunken 1560      >= 10000                 ~150 bytes
#define IRMP_SUPPORT_FDC_PROTOCOL               1       // FDC3402 keyboard     >= 10000 (better 15000)  ~150 bytes (~400 in combination with RC5)
#define IRMP_SUPPORT_RCCAR_PROTOCOL             1       // RC Car               >= 10000 (better 15000)  ~150 bytes (~500 in combination with RC5)
#define IRMP_SUPPORT_ROOMBA_PROTOCOL            0       // iRobot Roomba        >= 10000                 ~150 bytes
#define IRMP_SUPPORT_RUWIDO_PROTOCOL            0       // RUWIDO, T-Home       >= 15000                 ~550 bytes
#define IRMP_SUPPORT_A1TVBOX_PROTOCOL           1       // A1 TV BOX            >= 15000 (better 20000)  ~300 bytes
#define IRMP_SUPPORT_LEGO_PROTOCOL              1       // LEGO Power RC        >= 20000                 ~150 bytes
#define IRMP_SUPPORT_RCMM_PROTOCOL              1       // RCMM 12,24, or 32    >= 20000                 ~150 bytes
#define IRMP_SUPPORT_LGAIR_PROTOCOL             1       // LG Air Condition     >= 10000                 ~300 bytes
#define IRMP_SUPPORT_SAMSUNG48_PROTOCOL         1       // Samsung48            >= 10000                 ~100 bytes (SAMSUNG must be enabled!)
#define IRMP_SUPPORT_MERLIN_PROTOCOL            0       // Merlin               >= 15000 (better 20000)  ~300 bytes
#define IRMP_SUPPORT_PENTAX_PROTOCOL            0       // Pentax               >= 10000                 ~150 bytes
#define IRMP_SUPPORT_S100_PROTOCOL              0       // S100                 >= 10000                 ~250 bytes
#define IRMP_SUPPORT_ACP24_PROTOCOL             0       // ACP24                >= 10000                 ~250 bytes
#define IRMP_SUPPORT_TECHNICS_PROTOCOL          1       // TECHNICS             >= 10000                 ~250 bytes
#define IRMP_SUPPORT_PANASONIC_PROTOCOL         0       // PANASONIC Beamer     >= 10000                 ~250 bytes
#define IRMP_SUPPORT_MITSU_HEAVY_PROTOCOL       1       // Mitsubishi Aircond   >= 10000                 ~250 bytes
#define IRMP_SUPPORT_VINCENT_PROTOCOL           1       // VINCENT              >= 10000                 ~250 bytes
#define IRMP_SUPPORT_SAMSUNGAH_PROTOCOL         1       // SAMSUNG AH           >= 10000                 ~250 bytes
#define IRMP_SUPPORT_IRMP16_PROTOCOL            1       // IRMP specific        >= 15000                 ~250 bytes
#define IRMP_SUPPORT_GREE_PROTOCOL              0       // GREE CLIMATE         >= 10000                 ~250 bytes
#define IRMP_SUPPORT_RCII_PROTOCOL              0       // RCII T+A             >= 15000                 ~250 bytes
#define IRMP_SUPPORT_METZ_PROTOCOL              1       // METZ                 >= 15000                 ~250 bytes

#define IRMP_SUPPORT_RADIO1_PROTOCOL            0       // RADIO, e.g. TEVION   >= 10000                 ~250 bytes (experimental)

/*---------------------------------------------------------------------------------------------------------------------------------------------------
 * Change hardware pin here for ATMEL ATMega/ATTiny/XMega
 *---------------------------------------------------------------------------------------------------------------------------------------------------
 */
#if defined (ATMEL_AVR) || defined (__AVR_XMEGA__)                      // use PB6 as IR input on AVR
#  define IRMP_PORT_LETTER                      B
#  define IRMP_BIT_NUMBER                       6

/*---------------------------------------------------------------------------------------------------------------------------------------------------
 * Change hardware pin here for PIC C18 or XC8 compiler
 *---------------------------------------------------------------------------------------------------------------------------------------------------
 */
#elif defined (PIC_C18)                                                 // use RB4 as IR input on PIC (C18 or XC8 compiler)
#  if defined(__12F1840)
#    define IRMP_PIN                            RA5                     // on 12F1840 with XC8 compiler
#  else
#    define IRMP_PIN                            PORTBbits.RB4           // PIC C18
#  endif

/*---------------------------------------------------------------------------------------------------------------------------------------------------
 * Change hardware pin here for PIC CCS compiler
 *---------------------------------------------------------------------------------------------------------------------------------------------------
 */
#elif defined (PIC_CCS)
#  define IRMP_PIN                              PIN_B4                  // use PB4 as IR input on PIC (CCS compiler)

/*---------------------------------------------------------------------------------------------------------------------------------------------------
 * Change hardware pin here for ARM STM32
 *---------------------------------------------------------------------------------------------------------------------------------------------------
 */
#elif defined (ARM_STM32)                                               // use C13 as IR input on STM32
#  define IRMP_PORT_LETTER                      C
#  define IRMP_BIT_NUMBER                       13

/*---------------------------------------------------------------------------------------------------------------------------------------------------
 * Hardware pin for ARM STM32 (HAL) - don't change here, define IRMP_RECEIVE_GPIO_Port & IRMP_RECEIVE_PIN in STM32Cube (Main.h)
 *---------------------------------------------------------------------------------------------------------------------------------------------------
 */
#elif defined (ARM_STM32_HAL)                                           // STM32: IRMP_RECEIVE_GPIO_Port & IRMP_RECEIVE_PIN must be defined in STM32Cube
#  define IRMP_PORT_LETTER                      IRMP_Receive_GPIO_Port
#  define IRMP_BIT_NUMBER                       IRMP_Receive_Pin

/*---------------------------------------------------------------------------------------------------------------------------------------------------
 * Change hardware pin here for Stellaris ARM Cortex M4
 *---------------------------------------------------------------------------------------------------------------------------------------------------
 */
#elif defined (STELLARIS_ARM_CORTEX_M4)                                 // use B4 as IR input on Stellaris LM4F
#  define IRMP_PORT_LETTER                      B
#  define IRMP_BIT_NUMBER                       4

/*---------------------------------------------------------------------------------------------------------------------------------------------------
 * Change hardware pin here for STM8
 *---------------------------------------------------------------------------------------------------------------------------------------------------
 */
#elif defined (SDCC_STM8)                                               // use PA1 as IR input on STM8
#  define IRMP_PORT_LETTER                      A
#  define IRMP_BIT_NUMBER                       1

/*---------------------------------------------------------------------------------------------------------------------------------------------------
 * Change hardware pin here for ESP8266
 *---------------------------------------------------------------------------------------------------------------------------------------------------
 */
#elif defined (__xtensa__)
#  define IRMP_BIT_NUMBER                       12                      // use GPIO12 (Pin 7 UEXT) on ESP8266-EVB evaluation board

/*---------------------------------------------------------------------------------------------------------------------------------------------------
 * Change hardware pin here for Teensy 3.x with teensyduino gcc compiler
 *---------------------------------------------------------------------------------------------------------------------------------------------------
 */
#elif defined (TEENSY_ARM_CORTEX_M4)
#  define IRMP_PIN                              1                       // use Digital pin 1 as IR input on Teensy

/*---------------------------------------------------------------------------------------------------------------------------------------------------
 * Change hardware pin here for MBED
 *---------------------------------------------------------------------------------------------------------------------------------------------------
 */
#elif defined(__MBED__)
#  define IRMP_PIN                              P0_22                   // use P1_27 on LPC1347
#  define IRMP_PINMODE                          PullUp                  // hardware dependent

/*---------------------------------------------------------------------------------------------------------------------------------------------------
 * Change hardware pin here for ChibiOS HAL
 *---------------------------------------------------------------------------------------------------------------------------------------------------
 */
#elif defined(_CHIBIOS_HAL_)
#  define IRMP_PIN                              LINE_IR_IN              // use pin names as defined in the board config file, prefixed with "LINE_"
#  define IRMP_LOGGING_SD                       SD1                     // the ChibiOS HAL Serial Driver instance to log to
                                                                        // (when IRMP_LOGGING is enabled below). 
                                                                        // Make sure SERIAL_BUFFERS_SIZE is large enough when enabling logging

/*---------------------------------------------------------------------------------------------------------------------------------------------------
 * Handling of unknown target system: DON'T CHANGE
 *---------------------------------------------------------------------------------------------------------------------------------------------------
 */
#elif !defined (UNIX_OR_WINDOWS)
#  error target system not defined.
#endif

/*---------------------------------------------------------------------------------------------------------------------------------------------------
 * Set IRMP_LOGGING to 1 if want to log data to UART with 9600Bd
 *---------------------------------------------------------------------------------------------------------------------------------------------------
 */
#ifndef IRMP_LOGGING
#  define IRMP_LOGGING                          0       // 1: log IR signal (scan), 0: do not. default is 0
#endif

/*---------------------------------------------------------------------------------------------------------------------------------------------------
 * Use external logging routines
 * If you enable external logging, you have also to enable IRMP_LOGGING above
 *---------------------------------------------------------------------------------------------------------------------------------------------------
 */
#ifndef IRMP_EXT_LOGGING
#  define IRMP_EXT_LOGGING                      0       // 1: use external logging, 0: do not. default is 0
#endif

/*---------------------------------------------------------------------------------------------------------------------------------------------------
 * Set IRMP_PROTOCOL_NAMES to 1 if want to access protocol names (for logging etc), costs ~300 bytes RAM!
 *---------------------------------------------------------------------------------------------------------------------------------------------------
 */
#ifndef IRMP_PROTOCOL_NAMES
#  define IRMP_PROTOCOL_NAMES                   0       // 1: access protocol names, 0: do not. default is 0
#endif

/*---------------------------------------------------------------------------------------------------------------------------------------------------
 * Use Callbacks to indicate input signal
 *---------------------------------------------------------------------------------------------------------------------------------------------------
 */
#ifndef IRMP_USE_CALLBACK
#  define IRMP_USE_CALLBACK                     0       // 1: use callbacks. 0: do not. default is 0
#endif

/*---------------------------------------------------------------------------------------------------------------------------------------------------
 * Call the user-provided irmp_idle() function when IRMP is idle.
 * Can be used to disable the timer irq and enter a sleep mode to save power
 *---------------------------------------------------------------------------------------------------------------------------------------------------
 */
#ifndef IRMP_USE_IDLE_CALL
#  define IRMP_USE_IDLE_CALL                    0       // 1: use idle calls. 0: do not. default is 0
#endif

/*---------------------------------------------------------------------------------------------------------------------------------------------------
 * Use ChibiOS Events to signal that valid IR data was received
 *---------------------------------------------------------------------------------------------------------------------------------------------------
 */
#if defined(_CHIBIOS_RT_) || defined(_CHIBIOS_NIL_)

#  ifndef IRMP_USE_EVENT
#    define IRMP_USE_EVENT                      0       // 1: use event. 0: do not. default is 0
#  endif

#  if IRMP_USE_EVENT == 1 && !defined(IRMP_EVENT_BIT)
#    define IRMP_EVENT_BIT                      1                     // event flag or bit to send
#  endif
#  if IRMP_USE_EVENT == 1 && !defined(IRMP_EVENT_THREAD_PTR)
#    define IRMP_EVENT_THREAD_PTR               ir_receive_thread_p   // pointer to the thread to send the event to
extern thread_t *IRMP_EVENT_THREAD_PTR;                               // the pointer must be defined and initialized elsewhere
#  endif

#endif // _CHIBIOS_RT_ || _CHIBIOS_NIL_

#endif // _IRMPCONFIG_STAGE2_H_
