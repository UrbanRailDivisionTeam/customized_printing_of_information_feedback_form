function didMount() {
    var self = this;
    var dom = document.getElementById('crrc_baritemap');
    if (dom) {
        // 创建新元素替换旧元素（彻底移除所有监听器）
        var newDom = dom.cloneNode(true);
        dom.parentNode.replaceChild(newDom, dom);
        // 挂载新事件
        newDom.addEventListener('click', function (e) {
            // ========== 1. 获取表单元数据 ==========
            var meta = self.getFormMeta();
            console.log('[META] 表单ID:', meta.id);
            console.log('[META] 表单类型:', meta.type);
            // ========== 2. 递归提取所有 fieldcon 控件标识 ==========
            var allFields = [];
            function traverse(items, path) {
                if (!Array.isArray(items)) return;
                path = path || '';
                items.forEach(function (item, idx) {
                    var currentPath = path ? path + ' > ' + (item.id || idx) : (item.id || idx);
                    // 只收集业务字段控件（fieldcon）
                    if (item.type === 'fieldcon' && item.id) {
                        allFields.push({
                            id: item.id,
                            caption: item.caption && item.caption.zh_CN ? item.caption.zh_CN : item.id,
                            fieldType: item.item ? item.item.type : '',
                            required: item.mi === true || (item.item && item.item.mi === true),
                            fullLine: item.fullLine || false
                        });
                    }
                    // 递归遍历子节点
                    if (item.items && item.items.length > 0) {
                        traverse(item.items, currentPath);
                    }
                });
            }
            traverse(meta.items);
            // ========== 3. 提取所有 fieldcon 控件的当前值 ==========
            allFields.forEach(function (field) {
                try {
                    var value_dom = document.getElementById(field.id);
                    // 1. 优先找 input，取第一个
                    var input = value_dom.querySelector('input');
                    if (input) {
                        field.value = input.value;
                        console.log(field.id + ' (input):', field.value);
                        return;
                    }
                    // 2. 没找到 input，找 span，取最深层嵌套的
                    var span = value_dom.querySelector('span');
                    if (span) {
                        var deepestSpan = span;
                        // 循环向下查找，直到没有子 span 为止
                        while (deepestSpan.querySelector('span')) {
                            deepestSpan = deepestSpan.querySelector('span');
                        }
                        field.value = deepestSpan.textContent || deepestSpan.innerText || '';
                        console.log(field.id + ' (span 最深层):', field.value);
                        return;
                    }
                    // 3. 都没找到
                    field.value = null;
                    console.warn('[' + field.id + '] 未找到 input 或 span');
                } catch (e) {
                    console.warn('[' + field.id + '] 取值异常:', e.message);
                }
            });

            // ========== 3. 打印字段清单 ==========
            console.group('[FIELD] 业务字段清单 (共 ' + allFields.length + ' 个)');
            console.table(allFields.map(function (f) {
                return {
                    控件标识: f.id,
                    标题: f.caption,
                    控件类型: f.fieldType,
                    必填: f.required ? '是' : '否',
                    值: f.value
                };
            }));
            console.groupEnd();

            var API_URL = 'http://10.24.5.54:12377/api/sync';  // 请替换为实际接口
            var payload = {
                formId: meta.id,
                formType: meta.type,
                fields: allFields
            };
            fetch(API_URL, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            })
                .then(function (response) {
                    if (!response.ok) {
                        throw new Error('HTTP ' + response.status + ' ' + response.statusText);
                    }
                    return response.blob();
                })
                .then(function (blob) {
                    var url = window.URL.createObjectURL(blob);

                    // 创建隐藏 iframe 用于打印 PDF
                    var iframe = document.createElement('iframe');
                    iframe.style.display = 'none';
                    iframe.src = url;
                    iframe.onload = function () {
                        try {
                            setTimeout(function () {
                                iframe.contentWindow.focus();
                                iframe.contentWindow.print();
                            }, 500);
                        } catch (e) {
                            console.error('[ERROR] 打印失败:', e);
                            if (typeof self.showMessage === 'function') {
                                self.showMessage('打印失败: ' + e.message, 'error');
                            }
                        }
                        // 延迟清理 iframe，等待打印对话框
                        setTimeout(function () {
                            document.body.removeChild(iframe);
                            window.URL.revokeObjectURL(url);
                        }, 60000);
                    };
                    document.body.appendChild(iframe);

                    console.log('[SUCCESS] PDF 打印已触发');
                    if (typeof self.showMessage === 'function') {
                        self.showMessage('PDF 已生成，正在打印');
                    }
                })
                .catch(function (err) {
                    console.error('[ERROR] 发送失败:', err);
                    if (typeof self.showMessage === 'function') {
                        self.showMessage('数据同步失败: ' + err.message, 'error');
                    }
                });
        });
    }
}