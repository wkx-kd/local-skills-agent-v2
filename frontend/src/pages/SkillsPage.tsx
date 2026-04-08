import { useState, useEffect } from 'react';
import {
  Card, Table, Switch, Button, Tag, Typography, Space, Modal, Form, Input,
  message, Tabs, List, Checkbox, Divider, Popconfirm, Upload
} from 'antd';
import {
  ArrowLeftOutlined, PlusOutlined, GithubOutlined, UploadOutlined,
  DeleteOutlined, ReloadOutlined, FolderOutlined
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useSkillStore } from '../stores/skillStore';
import { useAuth } from '../hooks/useAuth';
import { skillsApi } from '../api/skills';
import { useIsMobile } from '../hooks/useIsMobile';
import type { Skill, SkillGroup } from '../types/skill';

const { Title, Text } = Typography;

export default function SkillsPage() {
  useAuth();
  const navigate = useNavigate();
  const isMobile = useIsMobile();
  const { skills, skillGroups, fetchSkills, fetchSkillGroups, toggleSkill } = useSkillStore();

  const [installModalOpen, setInstallModalOpen] = useState(false);
  const [groupModalOpen, setGroupModalOpen] = useState(false);
  const [editingGroup, setEditingGroup] = useState<SkillGroup | null>(null);
  const [installForm] = Form.useForm();
  const [groupForm] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [groupLoading, setGroupLoading] = useState(false);

  useEffect(() => {
    fetchSkills();
    fetchSkillGroups();
  }, [fetchSkills, fetchSkillGroups]);

  const handleRefresh = async () => {
    setLoading(true);
    try {
      await skillsApi.refresh();
      await fetchSkills();
      message.success('Skill 列表已刷新（已扫描 skills/ 目录）');
    } catch (e: any) {
      message.error(e.response?.data?.detail || '刷新失败');
    } finally {
      setLoading(false);
    }
  };

  const handleInstallGit = async (values: { url: string }) => {
    setLoading(true);
    try {
      await skillsApi.installGit(values.url);
      await fetchSkills();
      message.success('Skill 安装成功');
      setInstallModalOpen(false);
      installForm.resetFields();
    } catch (e: any) {
      message.error(e.response?.data?.detail || '安装失败');
    } finally {
      setLoading(false);
    }
  };

  const handleUninstall = async (skillId: string, skillName: string) => {
    try {
      await skillsApi.uninstall(skillId);
      await fetchSkills();
      message.success(`Skill "${skillName}" 已卸载`);
    } catch (e: any) {
      message.error(e.response?.data?.detail || '卸载失败');
    }
  };

  const handleSubmitGroup = async (values: { name: string; description?: string; skillIds?: string[] }) => {
    setGroupLoading(true);
    try {
      if (editingGroup) {
        await skillsApi.updateGroup(editingGroup.id, {
          name: values.name,
          description: values.description,
          skill_ids: values.skillIds ?? [],
        });
        message.success('分组已更新');
      } else {
        await skillsApi.createGroup({
          name: values.name,
          description: values.description,
          skill_ids: values.skillIds ?? [],
        });
        message.success('分组创建成功');
      }
      await fetchSkillGroups();
      setGroupModalOpen(false);
      setEditingGroup(null);
      groupForm.resetFields();
    } catch (e: any) {
      message.error(e.response?.data?.detail || (editingGroup ? '更新失败' : '创建失败'));
    } finally {
      setGroupLoading(false);
    }
  };

  const handleDeleteGroup = async (groupId: string) => {
    try {
      await skillsApi.deleteGroup(groupId);
      await fetchSkillGroups();
      message.success('分组已删除');
    } catch (e: any) {
      message.error(e.response?.data?.detail || '删除失败');
    }
  };

  const openEditGroup = (group: SkillGroup) => {
    setEditingGroup(group);
    groupForm.setFieldsValue({
      name: group.name,
      description: group.description,
      skillIds: group.skills.map(s => s.id),
    });
    setGroupModalOpen(true);
  };

  const openCreateGroup = () => {
    setEditingGroup(null);
    groupForm.resetFields();
    setGroupModalOpen(true);
  };

  const skillColumns = [
    { title: '名称', dataIndex: 'name', key: 'name', width: 150 },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
    { title: '版本', dataIndex: 'version', key: 'version', width: 80 },
    {
      title: '来源',
      dataIndex: 'source_type',
      key: 'source_type',
      width: 80,
      render: (type: string) => <Tag color={type === 'git' ? 'blue' : 'green'}>{type}</Tag>,
    },
    {
      title: '状态',
      key: 'is_active',
      width: 80,
      render: (_: any, record: Skill) => (
        <Switch checked={record.is_active} onChange={() => toggleSkill(record.id)} />
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 80,
      render: (_: any, record: Skill) => (
        <Popconfirm
          title={`确定卸载 Skill "${record.name}"？`}
          onConfirm={() => handleUninstall(record.id, record.name)}
        >
          <Button type="text" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      ),
    },
  ];

  // 移动端 Skill 卡片列表
  const SkillCardList = () => (
    <List
      dataSource={skills}
      locale={{ emptyText: '暂无已安装的 Skill' }}
      renderItem={(skill) => (
        <List.Item style={{ padding: '8px 0' }}>
          <Card
            size="small"
            style={{ width: '100%', background: '#2a2b2f', border: '1px solid #444746', borderRadius: 12 }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, flexWrap: 'wrap' }}>
                  <Text strong style={{ color: '#e3e3e3' }}>{skill.name}</Text>
                  <Tag color={skill.source_type === 'git' ? 'blue' : 'green'} style={{ margin: 0 }}>
                    {skill.source_type}
                  </Tag>
                  {skill.version && (
                    <Text type="secondary" style={{ fontSize: 11 }}>v{skill.version}</Text>
                  )}
                </div>
                {skill.description && (
                  <Text type="secondary" style={{ fontSize: 12, display: 'block' }}>
                    {skill.description}
                  </Text>
                )}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginLeft: 8, flexShrink: 0 }}>
                <Switch
                  size="small"
                  checked={skill.is_active}
                  onChange={() => toggleSkill(skill.id)}
                />
                <Popconfirm
                  title={`确定卸载 "${skill.name}"？`}
                  onConfirm={() => handleUninstall(skill.id, skill.name)}
                >
                  <Button type="text" danger size="small" icon={<DeleteOutlined />} />
                </Popconfirm>
              </div>
            </div>
          </Card>
        </List.Item>
      )}
    />
  );

  return (
    <div style={{ padding: isMobile ? '16px 12px' : 24, maxWidth: '100%', minHeight: '100vh', background: '#131314' }}>
      <div style={{ maxWidth: 1200, margin: '0 auto' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/')} type="default">
            返回
          </Button>
          <Title level={isMobile ? 5 : 4} style={{ margin: 0, color: '#e3e3e3' }}>
            Skill 管理
          </Title>
        </div>

        <Tabs
          items={[
            {
              key: 'skills',
              label: '已安装',
              children: (
                <Card style={{ borderRadius: 16, background: '#1e1f20', border: 'none' }}>
                  <div style={{ marginBottom: 16, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    <Button
                      type="primary"
                      icon={<PlusOutlined />}
                      onClick={() => setInstallModalOpen(true)}
                    >
                      安装 Skill
                    </Button>
                    <Button icon={<ReloadOutlined />} onClick={handleRefresh} loading={loading}>
                      扫描本地目录
                    </Button>
                  </div>
                  {isMobile ? (
                    <SkillCardList />
                  ) : (
                    <Table
                      dataSource={skills}
                      columns={skillColumns}
                      rowKey="id"
                      pagination={false}
                      loading={loading}
                    />
                  )}
                </Card>
              ),
            },
            {
              key: 'groups',
              label: 'Skill 分组',
              children: (
                <Card style={{ borderRadius: 16, background: '#1e1f20', border: 'none' }}>
                  <div style={{ marginBottom: 16 }}>
                    <Button type="primary" icon={<PlusOutlined />} onClick={openCreateGroup}>
                      创建分组
                    </Button>
                  </div>
                  <List
                    dataSource={skillGroups}
                    locale={{ emptyText: '暂无分组，点击"创建分组"添加' }}
                    renderItem={(group) => (
                      <List.Item
                        actions={
                          isMobile ? undefined : [
                            <Button type="link" onClick={() => openEditGroup(group)}>编辑</Button>,
                            <Popconfirm
                              title={`确定删除分组 "${group.name}"？`}
                              onConfirm={() => handleDeleteGroup(group.id)}
                            >
                              <Button type="link" danger>删除</Button>
                            </Popconfirm>,
                          ]
                        }
                      >
                        <List.Item.Meta
                          avatar={<FolderOutlined style={{ fontSize: 24, color: '#1890ff' }} />}
                          title={
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <Text style={{ color: '#e3e3e3' }}>{group.name}</Text>
                              {isMobile && (
                                <Space>
                                  <Button type="link" size="small" onClick={() => openEditGroup(group)}>编辑</Button>
                                  <Popconfirm
                                    title={`确定删除分组 "${group.name}"？`}
                                    onConfirm={() => handleDeleteGroup(group.id)}
                                  >
                                    <Button type="link" size="small" danger>删除</Button>
                                  </Popconfirm>
                                </Space>
                              )}
                            </div>
                          }
                          description={
                            <Space wrap>
                              {group.description && <Text type="secondary">{group.description}</Text>}
                              {group.description && group.skills.length > 0 && <Divider type="vertical" />}
                              {group.skills.length === 0
                                ? <Text type="secondary">（暂无 Skill）</Text>
                                : group.skills.map(s => <Tag key={s.id} color="blue">{s.name}</Tag>)
                              }
                            </Space>
                          }
                        />
                      </List.Item>
                    )}
                  />
                </Card>
              ),
            },
          ]}
        />

        {/* 安装 Skill 弹窗 */}
        <Modal
          title="安装 Skill"
          open={installModalOpen}
          onCancel={() => { setInstallModalOpen(false); installForm.resetFields(); }}
          footer={null}
          style={isMobile ? { top: 20 } : undefined}
        >
          <Tabs
            items={[
              {
                key: 'git',
                label: 'Git 仓库',
                icon: <GithubOutlined />,
                children: (
                  <Form form={installForm} onFinish={handleInstallGit} layout="vertical">
                    <Form.Item
                      name="url"
                      label="Git 仓库 URL"
                      rules={[{ required: true, message: '请输入 Git 仓库 URL' }]}
                    >
                      <Input placeholder="https://github.com/user/skill-repo.git" />
                    </Form.Item>
                    <Form.Item>
                      <Button type="primary" htmlType="submit" loading={loading} block>
                        安装
                      </Button>
                    </Form.Item>
                  </Form>
                ),
              },
              {
                key: 'upload',
                label: '上传 ZIP',
                icon: <UploadOutlined />,
                children: (
                  <Upload
                    accept=".zip"
                    showUploadList={false}
                    beforeUpload={async (file) => {
                      setLoading(true);
                      try {
                        await skillsApi.installUpload(file);
                        await fetchSkills();
                        message.success('Skill 安装成功');
                        setInstallModalOpen(false);
                      } catch (e: any) {
                        message.error(e.response?.data?.detail || '安装失败');
                      } finally {
                        setLoading(false);
                      }
                      return false;
                    }}
                  >
                    <Button icon={<UploadOutlined />} loading={loading} block>
                      选择 ZIP 文件上传
                    </Button>
                  </Upload>
                ),
              },
            ]}
          />
        </Modal>

        {/* 创建/编辑分组弹窗 */}
        <Modal
          title={editingGroup ? `编辑分组：${editingGroup.name}` : '创建分组'}
          open={groupModalOpen}
          onCancel={() => {
            setGroupModalOpen(false);
            setEditingGroup(null);
            groupForm.resetFields();
          }}
          onOk={() => groupForm.submit()}
          okText={editingGroup ? '保存' : '创建'}
          confirmLoading={groupLoading}
          style={isMobile ? { top: 20 } : undefined}
        >
          <Form form={groupForm} onFinish={handleSubmitGroup} layout="vertical">
            <Form.Item
              name="name"
              label="分组名称"
              rules={[{ required: true, message: '请输入分组名称' }]}
            >
              <Input placeholder="如：数据分析、内容创作" />
            </Form.Item>
            <Form.Item name="description" label="描述（可选）">
              <Input.TextArea rows={2} placeholder="分组用途说明" />
            </Form.Item>
            <Form.Item name="skillIds" label="选择 Skill（可多选）">
              <Checkbox.Group style={{ width: '100%' }}>
                <Space direction="vertical" style={{ width: '100%' }}>
                  {skills.length === 0
                    ? <Text type="secondary">暂无已安装的 Skill</Text>
                    : skills.map(s => (
                        <Checkbox key={s.id} value={s.id}>
                          <Space>
                            {s.name}
                            <Text type="secondary" style={{ fontSize: 12 }}>{s.description}</Text>
                            {!s.is_active && <Tag color="default">已禁用</Tag>}
                          </Space>
                        </Checkbox>
                      ))
                  }
                </Space>
              </Checkbox.Group>
            </Form.Item>
          </Form>
        </Modal>
      </div>
    </div>
  );
}
