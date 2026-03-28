/*
 * ATmega328PB telemetry receiver
 *
 * USART0 is used for the local serial monitor.
 * USART1 is used for the radio air module.
 *
 * Expected baud rate from the Python test script:
 *   9600 8N1
 *
 * Wiring:
 *   Radio TX  -> MCU RXD1 (PB4)
 *   Radio RX  -> MCU TXD1 (PB3)
 *   Radio GND -> MCU GND
 *
 * For a USB serial monitor:
 *   USB RX -> MCU TXD0 (PD1)
 *   USB TX -> MCU RXD0 (PD0)   // optional for future commands
 *   USB GND -> MCU GND
 */

#include <xc.h>
#include <avr/wdt.h>
#include <stdint.h>

#ifndef F_CPU
#define F_CPU 16000000UL
#endif

#define UART_BAUD_RATE 9600UL
#define UART_UBRR_VALUE ((F_CPU / (16UL * UART_BAUD_RATE)) - 1UL)
#define RX_MESSAGE_BUFFER_SIZE 64U

static void uart0_init(void)
{
    /* USART0 -> serial monitor */
    UBRR0H = (uint8_t)(UART_UBRR_VALUE >> 8);
    UBRR0L = (uint8_t)UART_UBRR_VALUE;
    UCSR0A = 0U;
    UCSR0B = (1 << RXEN0) | (1 << TXEN0);
    UCSR0C = (1 << UCSZ01) | (1 << UCSZ00);
}

static void uart1_init(void)
{
    /* USART1 -> telemetry radio */
    UBRR1H = (uint8_t)(UART_UBRR_VALUE >> 8);
    UBRR1L = (uint8_t)UART_UBRR_VALUE;
    UCSR1A = 0U;
    UCSR1B = (1 << RXEN1) | (1 << TXEN1);
    UCSR1C = (1 << UCSZ11) | (1 << UCSZ10);
}

static void uart0_write_char(char c)
{
    while ((UCSR0A & (1 << UDRE0)) == 0U) {
    }

    UDR0 = (uint8_t)c;
}

static void uart0_write_string(const char *text)
{
    while (*text != '\0') {
        uart0_write_char(*text++);
    }
}

static void uart0_write_line(const char *text)
{
    uart0_write_string(text);
    uart0_write_string("\r\n");
}

static uint8_t uart1_byte_available(void)
{
    return (UCSR1A & (1 << RXC1)) != 0U;
}

static uint8_t uart1_read_byte(void)
{
    return UDR1;
}

int main(void)
{
    uint8_t rx_byte = 0U;
    uint8_t rx_index = 0U;
    uint8_t saw_binary_data = 0U;
    char rx_message[RX_MESSAGE_BUFFER_SIZE];

    MCUSR = 0U;
    wdt_disable();

    uart0_init();
    uart1_init();

    uart0_write_line("Telemetry receiver ready");
    uart0_write_line("Listening on USART1 and printing to USART0");

    while (1) {
        if (uart1_byte_available() != 0U) {
            rx_byte = uart1_read_byte();

            if ((rx_byte >= 32U) && (rx_byte <= 126U)) {
                if (saw_binary_data != 0U) {
                    uart0_write_line("Received data");
                    saw_binary_data = 0U;
                }

                if (rx_index < (RX_MESSAGE_BUFFER_SIZE - 1U)) {
                    rx_message[rx_index++] = (char)rx_byte;
                }
            } else if ((rx_byte == '\r') || (rx_byte == '\n')) {
                if (rx_index > 0U) {
                    rx_message[rx_index] = '\0';
                    uart0_write_string("Received message: ");
                    uart0_write_line(rx_message);
                    rx_index = 0U;
                } else if (saw_binary_data != 0U) {
                    uart0_write_line("Received data");
                    saw_binary_data = 0U;
                }
            } else {
                if (rx_index > 0U) {
                    rx_message[rx_index] = '\0';
                    uart0_write_string("Received message: ");
                    uart0_write_line(rx_message);
                    rx_index = 0U;
                }

                saw_binary_data = 1U;
            }
        }
    }
}
