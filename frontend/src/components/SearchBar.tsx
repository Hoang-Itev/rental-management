import { useState, useEffect } from 'react';

interface Props {
  onSearch: (keyword: string) => void;
  placeholder?: string;
  initialValue?: string;
}

export function SearchBar({ onSearch, placeholder = 'Tìm kiếm...', initialValue = '' }: Props) {
  const [keyword, setKeyword] = useState(initialValue);

  useEffect(() => {
    const timer = setTimeout(() => {
      onSearch(keyword.trim());
    }, 400);
    return () => clearTimeout(timer);
  }, [keyword, onSearch]);

  return (
    <div className="search-bar">
      <input
        type="text"
        value={keyword}
        onChange={(e) => setKeyword(e.target.value)}
        placeholder={placeholder}
      />
    </div>
  );
}