'use client';

import { Button, Checkbox, ColorInput, Flex, Grid, TextInput } from '@mantine/core';
import { UseFormReturnType, useForm } from '@mantine/form';
import React, { useEffect } from 'react'
import { saveSettings, validateScrubbingSettings } from '../utils';

type Props = {
    settings: Record<string, string>,
}

export const Form = ({
    settings,
}: Props) => {
    const form = useForm({
        initialValues: getSettingsCopy(settings),
        validate: (values) => {
            return validateScrubbingSettings(values);
        },
    })

    useEffect(() => {
        form.setValues(getSettingsCopy(settings));
        form.setInitialValues(getSettingsCopy(settings));
    }, [settings]);

    function resetForm() {
        form.reset();
    }

    function _onSubmit(values: Record<string, string>) {
        saveSettings(form)({
            ...values,
            SCRUB_FILL_COLOR: convertHexToBGRInt(values.SCRUB_FILL_COLOR),
        });
    }

    return (
        <form onSubmit={form.onSubmit(_onSubmit)}>
            <Grid>
                <Grid.Col span={6}>
                    <Checkbox label="Scrubbing Enabled" {...form.getInputProps('SCRUB_ENABLED')} />
                </Grid.Col>
                <Grid.Col span={6}>
                    <TextInput label="Scrubbing character" placeholder="Scrubbing character" {...form.getInputProps('SCRUB_CHAR')} />
                </Grid.Col>
                <Grid.Col span={6}>
                    <TextInput label="Scrubbing language" placeholder="Scrubbing language" {...form.getInputProps('SCRUB_LANGUAGE')} />
                </Grid.Col>
                <Grid.Col span={6}>
                    <ColorInput label="Scrubbing fill color" placeholder="Scrubbing fill color" {...form.getInputProps('SCRUB_FILL_COLOR')} />
                </Grid.Col>
            </Grid>
            <Flex mt={40} columnGap={20}>
                <Button disabled={!form.isDirty()} type="submit">
                    Save settings
                </Button>
                <Button variant="subtle" disabled={!form.isDirty()} onClick={resetForm}>
                    Discard changes
                </Button>
            </Flex>
        </form>
    )
}

function toHex(value: number): string {
    return value.toString(16).padStart(2, '0');
}

function toInt(value: string): number {
    return parseInt(value, 16);
}

function convertBGRIntToHex(color: number): string {
    const r = color & 255;
    const g = (color >> 8) & 255;
    const b = (color >> 16) & 255;
    return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}

function convertHexToBGRInt(color: string): number {
    const hex = color.replace('#', '');
    const r = toInt(hex.slice(0, 2));
    const g = toInt(hex.slice(2, 4));
    const b = toInt(hex.slice(4, 6));
    return r | (g << 8) | (b << 16);
}

function getSettingsCopy(settings: Record<string, string>) {
    return JSON.parse(JSON.stringify({
        ...settings,
        SCRUB_FILL_COLOR: convertBGRIntToHex(parseInt(settings.SCRUB_FILL_COLOR)),
    }));
}
