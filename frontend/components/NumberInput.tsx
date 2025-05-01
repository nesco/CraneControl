'use client';
import React from 'react';

type BindFn = (fieldName: string) => React.InputHTMLAttributes<HTMLInputElement>;

export interface NumberInputProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type' | 'name'> {
  name: string;
  label: string;
  binding: BindFn;


}

export default function NumberInput({name, label, binding, className = '', ...rest}: NumberInputProps) {
  return (
        <div className="mb-4">
        <label htmlFor={name} className="block text-sm font-medium text-gray-700 dark:text-gray-100">{label}</label>
        <input 
          id={name} 
          name={name} 
          type="number" 
          step="any"
          className={`
          mt-1 block w-full rounded-md border-gray-300 shadow-sm
          focus:border-indigo-500 focus:ring-indigo-500
          dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100
          ${className}
          `} 
          {...binding(name)} 
          {...rest}
          placeholder={label} />
        </div>
  ) 
}
