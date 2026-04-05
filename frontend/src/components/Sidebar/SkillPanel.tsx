import { useEffect } from 'react';
import { Select, Tag, Typography, Button } from 'antd';
import { AppstoreOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useSkillStore } from '../../stores/skillStore';

const { Text } = Typography;

export default function SkillPanel() {
  const { skills, skillGroups, selectedGroupId, fetchSkills, fetchSkillGroups, setSelectedGroupId } = useSkillStore();
  const navigate = useNavigate();

  useEffect(() => {
    fetchSkills();
    fetchSkillGroups();
  }, [fetchSkills, fetchSkillGroups]);

  const activeSkills = selectedGroupId
    ? skillGroups.find((g) => g.id === selectedGroupId)?.skills || []
    : skills.filter((s) => s.is_active);

  return (
    <div style={{ padding: '12px 16px', borderTop: '1px solid #f0f0f0' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <Text strong>Skill 分组</Text>
        <Button 
          type="text" 
          size="small"
          icon={<AppstoreOutlined />} 
          onClick={() => navigate('/skills')}
          style={{ color: '#1890ff', fontSize: '12px' }}
        >
          管理
        </Button>
      </div>
      <Select
        value={selectedGroupId}
        onChange={setSelectedGroupId}
        allowClear
        placeholder="全部 Skill"
        style={{ width: '100%', marginBottom: 8 }}
        options={skillGroups.map((g) => ({ label: g.name, value: g.id }))}
      />
      <div>
        {activeSkills.map((s) => (
          <Tag key={s.id} color="blue" style={{ marginBottom: 4 }}>
            {s.name}
          </Tag>
        ))}
      </div>
    </div>
  );
}
