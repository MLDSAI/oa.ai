'use client'

import React, { useEffect } from 'react'
import { useForm } from '@mantine/form'
import { saveSettings } from '../utils'

type Props = {
    settings: Record<string, string>
}

export const Form = ({ settings }: Props) => {
    const form = useForm({
        initialValues: JSON.parse(JSON.stringify(settings)),
    })

    useEffect(() => {
        form.setValues(JSON.parse(JSON.stringify(settings)))
        form.setInitialValues(JSON.parse(JSON.stringify(settings)))
    }, [settings])

    function resetForm() {
        form.reset()
    }

    const inputClasses =
        'w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all duration-200 bg-white'
    const labelClasses = 'block text-sm font-medium text-gray-700 mb-1'
    const fieldsetClasses =
        'border border-gray-200 rounded-xl p-6 bg-zinc-100 shadow-lg relative mt-2'
    const legendClasses =
        'absolute -top-3 bg-primary/80 px-2 text-sm font-semibold text-zinc-200 shadow-lg rounded-lg'

    return (
        <form
            onSubmit={form.onSubmit(saveSettings(form))}
            className="max-w-6xl mx-auto p-6"
        >
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Privacy Section */}
                <div>
                    <fieldset className={fieldsetClasses}>
                        <legend className={legendClasses}>PRIVACY</legend>
                        <div className="space-y-4">
                            <div>
                                <label className={labelClasses}>
                                    PRIVATE_AI_API_KEY
                                </label>
                                <input
                                    type="text"
                                    placeholder="Please enter your Private AI API key"
                                    className={inputClasses}
                                    {...form.getInputProps(
                                        'PRIVATE_AI_API_KEY'
                                    )}
                                />
                            </div>
                        </div>
                    </fieldset>
                </div>

                {/* Segmentation Section */}
                <div>
                    <fieldset className={fieldsetClasses}>
                        <legend className={legendClasses}>SEGMENTATION</legend>
                        <div className="space-y-4">
                            <div>
                                <label className={labelClasses}>
                                    REPLICATE_API_TOKEN
                                </label>
                                <input
                                    type="text"
                                    placeholder="Please enter your Replicate API token"
                                    className={inputClasses}
                                    {...form.getInputProps(
                                        'REPLICATE_API_TOKEN'
                                    )}
                                />
                            </div>
                        </div>
                    </fieldset>
                </div>

                {/* Completions Section */}
                <div className="md:col-span-1">
                    <fieldset className={fieldsetClasses}>
                        <legend className={legendClasses}>COMPLETIONS</legend>
                        <div className="space-y-4">
                            <div>
                                <label className={labelClasses}>
                                    OPENAI_API_KEY
                                </label>
                                <input
                                    type="text"
                                    placeholder="Please enter your OpenAI API key"
                                    className={inputClasses}
                                    {...form.getInputProps('OPENAI_API_KEY')}
                                />
                            </div>
                            <div>
                                <label className={labelClasses}>
                                    ANTHROPIC_API_KEY
                                </label>
                                <input
                                    type="text"
                                    placeholder="Please enter your Anthropic API key"
                                    className={inputClasses}
                                    {...form.getInputProps('ANTHROPIC_API_KEY')}
                                />
                            </div>
                            <div>
                                <label className={labelClasses}>
                                    GOOGLE_API_KEY
                                </label>
                                <input
                                    type="text"
                                    placeholder="Please enter your Google API key"
                                    className={inputClasses}
                                    {...form.getInputProps('GOOGLE_API_KEY')}
                                />
                            </div>
                        </div>
                    </fieldset>
                </div>
            </div>

            {/* Buttons */}
            <div className="flex gap-4 mt-10">
                <button
                    type="submit"
                    disabled={!form.isDirty()}
                    className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors duration-200"
                >
                    Save settings
                </button>
                <button
                    type="button"
                    onClick={resetForm}
                    disabled={!form.isDirty()}
                    className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg disabled:text-gray-400 disabled:cursor-not-allowed transition-colors duration-200"
                >
                    Discard changes
                </button>
            </div>
        </form>
    )
}
