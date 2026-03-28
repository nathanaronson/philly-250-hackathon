/*
 * ATmega328PB 4-photodiode IR tracker
 *
 * Sensor layout:
 *   PC0 / ADC0 = top right
 *   PC1 / ADC1 = top left
 *   PC2 / ADC2 = bottom left
 *   PC3 / ADC3 = bottom right
 *
 * Lower voltage means brighter IR light.
 *
 * Startup flow:
 *   1. Measure a 5 second baseline with no intentional IR target.
 *   2. Prompt for a centered LED position.
 *   3. Wait 3 seconds and capture a centered response for gain trim.
 *
 * Runtime output prints signed horizontal and vertical offsets.
 */

#include <xc.h>
#include <avr/wdt.h>
#include <stdint.h>

#ifndef F_CPU
#define F_CPU 16000000UL
#endif

#define UART_BAUD_RATE               9600UL
#define UART_UBRR_VALUE              ((F_CPU / (16UL * UART_BAUD_RATE)) - 1UL)
#define ADC_REFERENCE_MV             5000UL
#define ADC_MAX_COUNT                1023UL
#define ADC_CHANNEL_COUNT            4U

#define BASELINE_TIME_MS             5000U
#define CENTER_WAIT_TIME_MS          3000U
#define CENTER_MEASURE_TIME_MS       2000U
#define SAMPLE_PERIOD_MS             20U
#define GAIN_SCALE                   256UL

static void delay_cycles(volatile uint32_t cycles)
{
    while (cycles-- != 0UL) {
        __asm__ volatile ("nop");
    }
}

static void delay_ms(uint16_t milliseconds)
{
    while (milliseconds-- != 0U) {
        delay_cycles(F_CPU / 4000UL);
    }
}

static void uart0_init(void)
{
    UBRR0H = (uint8_t)(UART_UBRR_VALUE >> 8);
    UBRR0L = (uint8_t)UART_UBRR_VALUE;

    UCSR0A = 0;
    UCSR0B = (1 << TXEN0);
    UCSR0C = (1 << UCSZ01) | (1 << UCSZ00);
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

static void uart0_write_u32(uint32_t value)
{
    char digits[10];
    uint8_t index = 0U;

    if (value == 0UL) {
        uart0_write_char('0');
        return;
    }

    while (value > 0UL) {
        digits[index++] = (char)('0' + (value % 10UL));
        value /= 10UL;
    }

    while (index > 0U) {
        uart0_write_char(digits[--index]);
    }
}

static void uart0_write_i32(int32_t value)
{
    if (value < 0L) {
        uart0_write_char('-');
        uart0_write_u32((uint32_t)(-value));
    } else {
        uart0_write_char('+');
        uart0_write_u32((uint32_t)value);
    }
}

static void adc_init(void)
{
    DIDR0 = (1 << ADC0D) | (1 << ADC1D) | (1 << ADC2D) | (1 << ADC3D);
    ADMUX = (1 << REFS0);
    ADCSRA = (1 << ADEN) | (1 << ADPS2) | (1 << ADPS1) | (1 << ADPS0);
}

static uint16_t adc_read(uint8_t channel)
{
    ADMUX = (ADMUX & 0xF0U) | (channel & 0x0FU);
    ADCSRA |= (1 << ADSC);

    while ((ADCSRA & (1 << ADSC)) != 0U) {
    }

    return ADC;
}

static void adc_read_all(uint16_t counts[ADC_CHANNEL_COUNT])
{
    uint8_t channel = 0U;

    for (channel = 0U; channel < ADC_CHANNEL_COUNT; channel++) {
        counts[channel] = adc_read(channel);
    }
}

static void average_channels_over_time(
    uint16_t duration_ms,
    uint16_t sample_period_ms,
    uint16_t averages[ADC_CHANNEL_COUNT]
)
{
    uint8_t channel = 0U;
    uint16_t sample = 0U;
    uint16_t sample_count = duration_ms / sample_period_ms;
    uint16_t counts[ADC_CHANNEL_COUNT];
    uint32_t sums[ADC_CHANNEL_COUNT] = {0UL, 0UL, 0UL, 0UL};

    if (sample_count == 0U) {
        sample_count = 1U;
    }

    for (sample = 0U; sample < sample_count; sample++) {
        adc_read_all(counts);

        for (channel = 0U; channel < ADC_CHANNEL_COUNT; channel++) {
            sums[channel] += counts[channel];
        }

        delay_ms(sample_period_ms);
    }

    for (channel = 0U; channel < ADC_CHANNEL_COUNT; channel++) {
        averages[channel] = (uint16_t)(sums[channel] / sample_count);
    }
}

static int16_t positive_delta(uint16_t baseline, uint16_t current)
{
    if (current < baseline) {
        return (int16_t)(baseline - current);
    }

    return 0;
}

static uint16_t baseline[ADC_CHANNEL_COUNT];
static uint16_t centered_counts[ADC_CHANNEL_COUNT];
static uint16_t counts[ADC_CHANNEL_COUNT];
static uint16_t raw_response_counts[ADC_CHANNEL_COUNT];
static uint16_t centered_response_counts[ADC_CHANNEL_COUNT];
static uint32_t corrected_signal[ADC_CHANNEL_COUNT];
static uint32_t gain_q8[ADC_CHANNEL_COUNT];

int main(void)
{
    uint8_t channel = 0U;
    uint32_t reference_response = 0UL;
    uint32_t total_signal = 0UL;
    uint32_t left_signal = 0UL;
    uint32_t right_signal = 0UL;
    uint32_t top_signal = 0UL;
    uint32_t bottom_signal = 0UL;
    int32_t x_error = 0L;
    int32_t y_error = 0L;

    MCUSR = 0U;
    wdt_disable();

    uart0_init();
    adc_init();

    uart0_write_line("IR tracker starting");
    uart0_write_line("Keep LED away");
    uart0_write_line("Baseline 5s");

    average_channels_over_time(BASELINE_TIME_MS, SAMPLE_PERIOD_MS, baseline);

    uart0_write_line("Center LED now");
    uart0_write_line("Waiting 3s");
    delay_ms(CENTER_WAIT_TIME_MS);
    uart0_write_line("Measuring gain");

    average_channels_over_time(CENTER_MEASURE_TIME_MS, SAMPLE_PERIOD_MS, centered_counts);

    for (channel = 0U; channel < ADC_CHANNEL_COUNT; channel++) {
        centered_response_counts[channel] =
            (uint16_t)positive_delta(baseline[channel], centered_counts[channel]);
        reference_response += centered_response_counts[channel];
    }

    reference_response /= ADC_CHANNEL_COUNT;

    if (reference_response == 0UL) {
        reference_response = 1UL;
    }

    for (channel = 0U; channel < ADC_CHANNEL_COUNT; channel++) {
        if (centered_response_counts[channel] == 0U) {
            gain_q8[channel] = GAIN_SCALE;
        } else {
            gain_q8[channel] =
                ((reference_response * GAIN_SCALE) + (centered_response_counts[channel] / 2UL)) /
                centered_response_counts[channel];
        }
    }

    uart0_write_line("Tracking started");

    while (1) {
        total_signal = 0UL;

        adc_read_all(counts);

        for (channel = 0U; channel < ADC_CHANNEL_COUNT; channel++) {
            raw_response_counts[channel] = (uint16_t)positive_delta(baseline[channel], counts[channel]);
            corrected_signal[channel] =
                ((uint32_t)raw_response_counts[channel] * gain_q8[channel]) / GAIN_SCALE;

            total_signal += corrected_signal[channel];
        }

        left_signal = corrected_signal[1] + corrected_signal[2];
        right_signal = corrected_signal[0] + corrected_signal[3];
        top_signal = corrected_signal[0] + corrected_signal[1];
        bottom_signal = corrected_signal[2] + corrected_signal[3];

        if (total_signal > 0UL) {
            x_error = (((int32_t)right_signal - (int32_t)left_signal) * 1000L) / (int32_t)total_signal;
            y_error = (((int32_t)top_signal - (int32_t)bottom_signal) * 1000L) / (int32_t)total_signal;
        } else {
            x_error = 0L;
            y_error = 0L;
        }

        if (total_signal == 0UL) {
            uart0_write_line("SEARCH");
        } else {
            uart0_write_string("H=");
            uart0_write_i32(x_error);
            uart0_write_string(" V=");
            uart0_write_i32(y_error);
            uart0_write_string("\r\n");
        }

        delay_ms(250U);
    }
}
