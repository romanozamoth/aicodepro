import { useState, useRef, useEffect } from 'react';
import { Textarea } from '@/components/ui/textarea';
import { Button, Spinner } from "@heroui/react";

interface ComposeBoxPlaygroundProps {
    handleUserMessage: (message: string) => void;
    messages: any[];
    loading: boolean;
    disabled?: boolean;
    shouldAutoFocus?: boolean;
    onFocus?: () => void;
}

export function ComposeBoxPlayground({
    handleUserMessage,
    messages,
    loading,
    disabled = false,
    shouldAutoFocus = false,
    onFocus,
}: ComposeBoxPlaygroundProps) {
    const [input, setInput] = useState('');
    const [isFocused, setIsFocused] = useState(false);
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const previousMessagesLength = useRef(messages.length);

    // Handle auto-focus when new messages arrive
    useEffect(() => {
        if (shouldAutoFocus && messages.length > previousMessagesLength.current && textareaRef.current) {
            textareaRef.current.focus();
        }
        previousMessagesLength.current = messages.length;
    }, [messages.length, shouldAutoFocus]);

    function handleInput() {
        const prompt = input.trim();
        if (!prompt) {
            return;
        }
        setInput('');
        handleUserMessage(prompt);
    }

    const handleInputKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleInput();
        }
    };

    const handleFocus = () => {
        setIsFocused(true);
        onFocus?.();
    };

    return (
        <div className="relative group">
            {/* Keyboard shortcut hint */}
            <div className="absolute -top-6 right-0 text-xs text-gray-500 dark:text-gray-400 opacity-0 
                          group-hover:opacity-100 transition-opacity">
                Press ⌘ + Enter to send
            </div>

            {/* Outer container with padding */}
            <div className="rounded-2xl border-[1.5px] border-gray-200 dark:border-[#2a2d31] p-3 relative 
                          bg-white dark:bg-[#1e2023] flex items-end gap-2">
                {/* Textarea */}
                <div className="flex-1">
                    <Textarea
                        ref={textareaRef}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleInputKeyDown}
                        onFocus={handleFocus}
                        onBlur={() => setIsFocused(false)}
                        disabled={disabled || loading}
                        placeholder="Type a message..."
                        autoResize={true}
                        maxHeight={120}
                        className={`
                            !min-h-0
                            !border-0 !shadow-none !ring-0
                            bg-transparent
                            resize-none
                            overflow-y-auto
                            [&::-webkit-scrollbar]:w-1
                            [&::-webkit-scrollbar-track]:bg-transparent
                            [&::-webkit-scrollbar-thumb]:bg-gray-300
                            [&::-webkit-scrollbar-thumb]:dark:bg-[#2a2d31]
                            [&::-webkit-scrollbar-thumb]:rounded-full
                            placeholder:text-gray-500 dark:placeholder:text-gray-400
                        `}
                    />
                </div>

                {/* Send button */}
                <Button
                    size="sm"
                    isIconOnly
                    disabled={disabled || loading || !input.trim()}
                    onPress={handleInput}
                    className={`
                        transition-all duration-200
                        ${input.trim() 
                            ? 'bg-indigo-50 hover:bg-indigo-100 text-indigo-700 dark:bg-indigo-900/50 dark:hover:bg-indigo-800/60 dark:text-indigo-300' 
                            : 'bg-gray-100 dark:bg-gray-800 text-gray-400 dark:text-gray-500'
                        }
                        scale-100 hover:scale-105 active:scale-95
                        disabled:opacity-50 disabled:scale-95
                        hover:shadow-md dark:hover:shadow-indigo-950/10
                        mb-0.5
                    `}
                >
                    {loading ? (
                        <Spinner size="sm" color={input.trim() ? "primary" : "default"} />
                    ) : (
                        <SendIcon 
                            size={16} 
                            className={`transform transition-transform ${isFocused ? 'translate-x-0.5' : ''}`}
                        />
                    )}
                </Button>
            </div>
        </div>
    );
}

// Custom SendIcon component for better visual alignment
function SendIcon({ size, className }: { size: number, className?: string }) {
    return (
        <svg 
            width={size} 
            height={size} 
            viewBox="0 0 24 24" 
            fill="none" 
            stroke="currentColor" 
            strokeWidth="2" 
            strokeLinecap="round" 
            strokeLinejoin="round"
            className={className}
        >
            <path d="M22 2L11 13" />
            <path d="M22 2L15 22L11 13L2 9L22 2Z" />
        </svg>
    );
} 