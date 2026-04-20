import React, { useState, useMemo } from 'react';
import { CheckCircle, AlertCircle, Download, Calendar } from 'lucide-react';

const InvoiceApp = () => {
  // 模拟数据结构：多层级（销方 -> 购方 -> 项目 -> 发票）
  const [invoices, setInvoices] = useState([
    {
      id: 'INV001',
      seller: '毅兴',
      buyer: '浙江省围海建设集团',
      project: '象山海塘改造二期',
      date: '2026-04-14',
      amount: 74025.00,
      paid: 0,
    },
    {
      id: 'INV002',
      seller: '旭达',
      buyer: '浙江良和交通建设',
      project: '象山大目湾道路工程',
      date: '2026-02-05',
      amount: 178594.00,
      paid: 0,
    }
  ]);

  const [activeSeller, setActiveSeller] = useState('毅兴');

  // 1. 逻辑优化：以购方为单位计算总额
  const buyerSummary = useMemo(() => {
    const filtered = invoices.filter(inv => inv.seller === activeSeller);
    const summary = {};
    filtered.forEach(inv => {
      if (!summary[inv.buyer]) {
        summary[inv.buyer] = { total: 0, paid: 0, projects: [] };
      }
      summary[inv.buyer].total += inv.amount;
      summary[inv.buyer].paid += inv.paid;
      summary[inv.buyer].projects.push(inv);
    });
    return summary;
  }, [invoices, activeSeller]);

  // 2. 自动核销处理逻辑
  const handlePayment = (id, val) => {
    setInvoices(prev => prev.map(inv => 
      inv.id === id ? { ...inv, paid: parseFloat(val) || 0 } : inv
    ));
  };

  return (
    <div className="flex h-screen bg-[#FDFCF9] font-sans text-gray-800">
      {/* 左侧侧边栏 - 一级目录（销方） */}
      <div className="w-20 bg-white border-r flex flex-col items-center py-8 gap-8">
        <div className="w-10 h-10 bg-black rounded-xl flex items-center justify-center text-white font-bold">F</div>
        {['毅兴', '旭达'].map(s => (
          <button 
            onClick={() => setActiveSeller(s)}
            className={`p-3 rounded-xl transition ${activeSeller === s ? 'bg-orange-100 text-orange-600' : 'hover:bg-gray-100'}`}
          >
            <span className="text-xs font-bold">{s}</span>
          </button>
        ))}
      </div>

      {/* 主内容区 */}
      <div className="flex-1 p-10 overflow-y-auto">
        <header className="flex justify-between items-center mb-10">
          <div>
            <h1 className="text-2xl font-bold">发票数据归纳 / {activeSeller}</h1>
            <p className="text-gray-400 text-sm">今日结清率: 85%</p>
          </div>
          <button className="flex items-center gap-2 bg-black text-white px-4 py-2 rounded-lg text-sm">
            <Download size={16} /> 导出 CSV
          </button>
        </header>

        {/* 二级目录：购方概览卡片 */}
        {Object.entries(buyerSummary).map(([buyerName, data]) => (
          <div key={buyerName} className="mb-8">
            <div className="flex justify-between items-end mb-4">
              <h2 className="text-lg font-bold">购方：{buyerName}</h2>
              <p className="text-sm text-gray-500">
                累计总额: <span className="font-mono font-bold text-black">￥{data.total.toLocaleString()}</span>
              </p>
            </div>

            {/* 三级目录：具体发票/项目项 */}
            <div className="grid grid-cols-1 gap-4">
              {data.projects.map(inv => {
                const balance = inv.amount - inv.paid;
                const isCleared = balance <= 0;
                const isOverdue = new Date(inv.date) < new Date(Date.now() - 30*24*60*60*1000);

                return (
                  <div key={inv.id} className={`bg-white p-6 rounded-2xl shadow-sm border transition ${isCleared ? 'opacity-60' : ''}`}>
                    <div className="flex justify-between items-start">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-xs bg-gray-100 px-2 py-1 rounded text-gray-500">{inv.id}</span>
                          <h3 className="font-bold text-gray-700">{inv.project}</h3>
                        </div>
                        <div className="flex gap-4 text-xs text-gray-400">
                          <span className="flex items-center gap-1"><Calendar size={12}/> {inv.date}</span>
                          {isOverdue && !isCleared && (
                            <span className="flex items-center gap-1 text-red-400 font-bold"><AlertCircle size={12}/> 超期预警</span>
                          )}
                        </div>
                      </div>

                      <div className="flex gap-8 items-center">
                        <div className="text-right">
                          <p className="text-xs text-gray-400">应收金额</p>
                          <p className="font-mono font-bold">￥{inv.amount.toLocaleString()}</p>
                        </div>
                        <div className="text-right">
                          <p className="text-xs text-gray-400">到账录入</p>
                          <input 
                            type="number"
                            placeholder="输入金额"
                            className="w-24 text-right border-b focus:outline-none focus:border-black font-mono"
                            onChange={(e) => handlePayment(inv.id, e.target.value)}
                          />
                        </div>
                        <div className="w-24 text-right">
                          <p className="text-xs text-gray-400">余额</p>
                          <p className={`font-mono font-bold ${balance > 0 ? 'text-orange-500' : 'text-green-500'}`}>
                            {isCleared ? '￥0.00' : `￥${balance.toLocaleString()}`}
                          </p>
                        </div>
                        <div className="ml-4">
                          {isCleared ? (
                            <CheckCircle className="text-green-500" />
                          ) : (
                            <div className="w-6 h-6 border-2 border-dashed border-gray-200 rounded-full" />
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default InvoiceApp;
